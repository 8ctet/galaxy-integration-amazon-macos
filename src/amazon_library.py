"""Amazon Games library (entitlements) client.

Verified against nile/api/library.py. The distribution endpoint authenticates
via the ``x-amzn-token`` header (NOT ``Authorization: bearer``) and is paged
through ``nextToken``.
"""

import hashlib
import logging

from consts import (
    ENTITLEMENTS_TARGET,
    ENTITLEMENTS_URL,
    HARDWARE_KEY_ID,
    SDS_USER_AGENT,
)

logger = logging.getLogger("amazon_plugin.library")

# Safety cap so a misbehaving server can never loop us forever (~50 games/page).
_MAX_PAGES = 200


class AmazonLibraryClient:
    def __init__(self, http_client):
        self._http = http_client

    async def get_entitlements(self, access_token, serial):
        """Return the de-duplicated list of raw entitlement dicts for the account."""
        headers = {
            "X-Amz-Target": ENTITLEMENTS_TARGET,
            "x-amzn-token": access_token,
            "UserAgent": SDS_USER_AGENT,
            "Content-Type": "application/json",
            "Content-Encoding": "amz-1.0",
        }
        hardware_hash = hashlib.sha256(serial.encode()).hexdigest().upper()

        by_id = {}
        next_token = None
        pages = 0
        while pages < _MAX_PAGES:
            pages += 1
            body = {
                "Operation": "GetEntitlements",
                "clientId": "Sonic",
                "syncPoint": None,
                "nextToken": next_token,
                "maxResults": 50,
                "productIdFilter": None,
                "keyId": HARDWARE_KEY_ID,
                "hardwareHash": hardware_hash,
            }
            resp = await self._http.request(
                "POST", ENTITLEMENTS_URL, headers=headers, json_body=body
            )
            if resp.status == 401:
                # Caller refreshes the token and retries.
                raise PermissionError("entitlements unauthorized (401)")
            if not resp.ok:
                logger.error("Entitlements request failed: HTTP %s", resp.status)
                raise RuntimeError("entitlements failed: HTTP %s" % resp.status)

            data = resp.json()
            for ent in data.get("entitlements", []):
                product = ent.get("product") or {}
                pid = product.get("id")
                if pid and pid not in by_id:
                    by_id[pid] = ent

            next_token = data.get("nextToken")
            if not next_token:
                break

        logger.info("Fetched %d entitlements across %d page(s)", len(by_id), pages)
        return list(by_id.values())
