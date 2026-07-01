"""Amazon OAuth2 + PKCE device authorization.

Flow (verified against nile/api/authorization.py):
  1. Generate a device serial, a PKCE verifier/challenge and a hex client id.
  2. Send the user to amazon.com/ap/signin; Amazon redirects back with an
     ``openid.oa2.authorization_code`` once login (incl. MFA) completes.
  3. Exchange that code at api.amazon.com/auth/register for bearer tokens.
  4. Refresh the access token at api.amazon.com/auth/token when it expires.

Token persistence is delegated to GOG Galaxy (Plugin.store_credentials), so we
do not encrypt or write tokens ourselves — only (de)serialise the in-memory
state to a plain dict.
"""

import base64
import hashlib
import logging
import secrets
import time
import uuid
from urllib.parse import urlencode

from consts import (
    AMAZON_REGISTER,
    AMAZON_SIGNIN,
    AMAZON_TOKEN,
    APP_NAME,
    APP_VERSION,
    ASSOC_HANDLE,
    DEVICE_MODEL,
    DEVICE_TYPE,
    MARKETPLACE_ID,
    OS_VERSION,
    RETURN_TO,
)

logger = logging.getLogger("amazon_plugin.auth")


class AmazonAuthError(Exception):
    """Raised when registration or refresh fails."""


class AmazonAuthClient:
    def __init__(self, http_client):
        self._http = http_client
        # Login material (set by prepare_login, consumed by register_device).
        self.serial = None
        self.client_id = None
        self._code_verifier = None
        # Token state (set by register_device / restore).
        self.access_token = None
        self.refresh_token = None
        self.expires_in = 0
        self.token_obtain_time = 0
        self.user_id = None
        self.user_name = None
        self.device_serial = None

    # -- login url -----------------------------------------------------------
    def prepare_login(self):
        """Generate PKCE material and return the Amazon sign-in URL."""
        self.serial = uuid.uuid1().hex.upper()
        self._code_verifier = base64.urlsafe_b64encode(
            secrets.token_bytes(32)
        ).rstrip(b"=")
        challenge = base64.urlsafe_b64encode(
            hashlib.sha256(self._code_verifier).digest()
        ).rstrip(b"=")
        self.client_id = f"{self.serial}#{DEVICE_TYPE}".encode("ascii").hex()
        return self._build_auth_url(self.client_id, challenge)

    @staticmethod
    def _build_auth_url(client_id, challenge):
        params = {
            "openid.ns": "http://specs.openid.net/auth/2.0",
            "openid.claimed_id": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.identity": "http://specs.openid.net/auth/2.0/identifier_select",
            "openid.mode": "checkid_setup",
            "openid.oa2.scope": "device_auth_access",
            "openid.ns.oa2": "http://www.amazon.com/ap/ext/oauth/2",
            "openid.oa2.response_type": "code",
            "openid.oa2.code_challenge_method": "S256",
            "openid.oa2.client_id": "device:" + client_id,
            "language": "en_US",
            "marketPlaceId": MARKETPLACE_ID,
            "openid.return_to": RETURN_TO,
            "openid.pape.max_auth_age": 0,
            "openid.assoc_handle": ASSOC_HANDLE,
            "pageId": ASSOC_HANDLE,
            "openid.oa2.code_challenge": challenge,
        }
        return AMAZON_SIGNIN + "?" + urlencode(params)

    # -- token exchange ------------------------------------------------------
    async def register_device(self, code):
        """Exchange the authorization code for bearer tokens."""
        if not (self.client_id and self._code_verifier and self.serial):
            raise AmazonAuthError("register_device called before prepare_login")
        body = {
            "auth_data": {
                "authorization_code": code,
                "client_domain": "DeviceLegacy",
                "client_id": self.client_id,
                "code_algorithm": "SHA-256",
                "code_verifier": self._code_verifier.decode("utf-8"),
                "use_global_authentication": False,
            },
            "registration_data": {
                "app_name": APP_NAME,
                "app_version": APP_VERSION,
                "device_model": DEVICE_MODEL,
                "device_name": None,
                "device_serial": self.serial,
                "device_type": DEVICE_TYPE,
                "domain": "Device",
                "os_version": OS_VERSION,
            },
            "requested_extensions": ["customer_info", "device_info"],
            "requested_token_type": ["bearer", "mac_dms"],
            "user_context_map": {},
        }
        resp = await self._http.request("POST", AMAZON_REGISTER, json_body=body)
        if not resp.ok:
            logger.error("Device registration failed: HTTP %s", resp.status)
            raise AmazonAuthError("registration failed: HTTP %s" % resp.status)

        try:
            success = resp.json()["response"]["success"]
            bearer = success["tokens"]["bearer"]
            customer = success["extensions"]["customer_info"]
        except (KeyError, ValueError) as exc:
            raise AmazonAuthError("unexpected register response: %s" % exc)

        self.access_token = bearer["access_token"]
        self.refresh_token = bearer["refresh_token"]
        self.expires_in = int(bearer.get("expires_in", 3600))
        self.token_obtain_time = time.time()
        # GOG's account-linking backend (external-accounts.gog.com) returns HTTP 500
        # on the raw Amazon user_id ("amzn1.account.XXXX" — dotted, non-numeric),
        # which blocks the library import. Every platform that works (Steam, PSN,
        # Xbox, Humble) reports a purely numeric id, so expose a stable numeric id
        # derived from the Amazon account id. The Amazon API itself never needs the
        # user_id (entitlements use the access token + device serial), so this is
        # purely the GOG-facing identity.
        self.amazon_user_id = customer["user_id"]
        self.user_id = str(int(hashlib.sha256(self.amazon_user_id.encode()).hexdigest()[:16], 16))
        self.user_name = customer.get("given_name") or "Amazon user"
        # Serial echoed back by the service; used for the entitlements hardwareHash.
        self.device_serial = (
            success.get("extensions", {})
            .get("device_info", {})
            .get("device_serial_number")
            or self.serial
        )
        logger.info("Device registered for user %s", self.user_id)
        return self.serialize()

    async def refresh(self):
        """Refresh the access token using the stored refresh token."""
        if not self.refresh_token:
            raise AmazonAuthError("no refresh token available")
        body = {
            "source_token": self.refresh_token,
            "source_token_type": "refresh_token",
            "requested_token_type": "access_token",
            "app_name": APP_NAME,
            "app_version": APP_VERSION,
        }
        resp = await self._http.request("POST", AMAZON_TOKEN, json_body=body)
        if not resp.ok:
            logger.error("Token refresh failed: HTTP %s", resp.status)
            raise AmazonAuthError("refresh failed: HTTP %s" % resp.status)
        data = resp.json()
        self.access_token = data["access_token"]
        self.expires_in = int(data.get("expires_in", 3600))
        self.token_obtain_time = time.time()
        # The refresh endpoint does not return a new refresh_token; keep the old one.
        logger.info("Access token refreshed")
        return self.serialize()

    # -- state (de)serialisation --------------------------------------------
    def is_expired(self, margin=60):
        if not self.token_obtain_time or not self.expires_in:
            return True
        return time.time() > self.token_obtain_time + self.expires_in - margin

    @property
    def hardware_serial(self):
        return self.device_serial or self.serial

    def serialize(self):
        return {
            "serial": self.serial,
            "client_id": self.client_id,
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "expires_in": self.expires_in,
            "token_obtain_time": self.token_obtain_time,
            "user_id": self.user_id,
            "user_name": self.user_name,
            "device_serial": self.device_serial,
        }

    def restore(self, creds):
        self.serial = creds.get("serial")
        self.client_id = creds.get("client_id")
        self.access_token = creds.get("access_token")
        self.refresh_token = creds.get("refresh_token")
        self.expires_in = int(creds.get("expires_in") or 0)
        self.token_obtain_time = float(creds.get("token_obtain_time") or 0)
        self.user_id = creds.get("user_id")
        self.user_name = creds.get("user_name")
        self.device_serial = creds.get("device_serial") or self.serial
