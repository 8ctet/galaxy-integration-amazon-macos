"""GOG Galaxy <-> Amazon Games integration (macOS, library sync only).

Implements the minimum surface that is achievable without the Windows-only
Amazon Games desktop client:
  * authenticate / pass_login_credentials  -> Amazon OAuth2+PKCE via web session
  * get_owned_games                          -> Amazon entitlements
  * get_local_games                          -> [] (no Amazon client on macOS)
  * get_os_compatibility                     -> Windows (Amazon titles are Win32)

Achievements, playtime and launch/install/uninstall are NOT implemented: Amazon
exposes no public API for the first two, and there is no Amazon Games client on
macOS for the rest. Those methods are absent, so Galaxy never advertises them.

IMPORTANT: authenticate() must return a NUMERIC user_id. GOG's account-linking
backend (external-accounts.gog.com) returns HTTP 500 on Amazon's raw dotted id
("amzn1.account.XXXX"), which silently blocks the entire import (the integration
shows "connected" then immediately "disconnected"). See amazon_auth.py.
"""

import logging
import sys
from urllib.parse import parse_qs, urlsplit

from galaxy.api.consts import LicenseType, OSCompatibility, Platform
from galaxy.api.errors import AuthenticationRequired, InvalidCredentials
from galaxy.api.plugin import Plugin, create_and_run_plugin
from galaxy.api.types import Authentication, Game, LicenseInfo, NextStep

from amazon_auth import AmazonAuthClient, AmazonAuthError
from amazon_library import AmazonLibraryClient
from http_client import HttpClient
from version import __version__

logger = logging.getLogger("amazon_plugin")

_AUTH_PARAMS = {
    "window_title": "Connexion à Amazon Games",
    "window_width": 560,
    "window_height": 710,
    # Amazon redirects to https://www.amazon.com/?...&openid.oa2.authorization_code=...
    # once login (and any MFA/captcha) completes. Anchor on the code so Galaxy
    # only hands control back when it is present.
    "end_uri_regex": r"^https://www\.amazon\.com/.*openid\.oa2\.authorization_code.*",
}


class AmazonPlugin(Plugin):
    def __init__(self, reader, writer, token):
        super().__init__(Platform.Amazon, __version__, reader, writer, token)
        self._http = HttpClient()
        self._auth = AmazonAuthClient(self._http)
        self._library = AmazonLibraryClient(self._http)

    # -- authentication ------------------------------------------------------
    async def authenticate(self, stored_credentials=None):
        if not stored_credentials:
            login_url = self._auth.prepare_login()
            params = dict(_AUTH_PARAMS, start_uri=login_url)
            return NextStep("web_session", params)

        # Restore path: rehydrate tokens persisted by Galaxy.
        self._auth.restore(stored_credentials)
        if not self._auth.refresh_token:
            raise InvalidCredentials()
        # Best-effort proactive refresh. Transient failures are deferred to the
        # first import (get_owned_games), which re-prompts via lost_authentication.
        try:
            if self._auth.is_expired():
                self.store_credentials(await self._auth.refresh())
        except Exception:  # noqa: BLE001 - never fail restore on a flaky network
            logger.warning("Proactive token refresh failed; will retry on import")
        return Authentication(self._auth.user_id, self._auth.user_name)

    async def pass_login_credentials(self, step, credentials, cookies):
        end_uri = credentials.get("end_uri", "")
        code = parse_qs(urlsplit(end_uri).query).get(
            "openid.oa2.authorization_code", [None]
        )[0]
        if not code:
            logger.error("No authorization code in redirect URL")
            raise InvalidCredentials()
        try:
            creds = await self._auth.register_device(code)
        except AmazonAuthError:
            logger.exception("Device registration failed")
            raise InvalidCredentials()
        self.store_credentials(creds)
        return Authentication(self._auth.user_id, self._auth.user_name)

    async def _refresh_or_drop(self):
        """Refresh the access token; on hard failure drop auth and re-prompt."""
        try:
            self.store_credentials(await self._auth.refresh())
        except AmazonAuthError:
            self.lost_authentication()
            raise AuthenticationRequired()

    async def _ensure_token(self):
        if not self._auth.refresh_token:
            raise AuthenticationRequired()
        if self._auth.is_expired():
            await self._refresh_or_drop()

    # -- owned games ---------------------------------------------------------
    async def get_owned_games(self):
        logger.info("get_owned_games: start")
        await self._ensure_token()
        try:
            entitlements = await self._library.get_entitlements(
                self._auth.access_token, self._auth.hardware_serial
            )
        except PermissionError:
            # 401 despite a non-expired token: refresh once and retry.
            logger.info("Entitlements returned 401; refreshing token and retrying")
            await self._refresh_or_drop()
            try:
                entitlements = await self._library.get_entitlements(
                    self._auth.access_token, self._auth.hardware_serial
                )
            except PermissionError:
                self.lost_authentication()
                raise AuthenticationRequired()
        games = [self._to_game(ent) for ent in entitlements]
        logger.info("get_owned_games: returning %d games", len(games))
        return games

    @staticmethod
    def _to_game(entitlement):
        product = entitlement.get("product") or {}
        game_id = product.get("id") or product.get("asin")
        title = product.get("title") or ("Amazon Game %s" % (game_id or "?"))
        return Game(game_id, title, None, LicenseInfo(LicenseType.SinglePurchase))

    # -- local games / OS compatibility -------------------------------------
    async def get_local_games(self):
        # No Amazon Games client exists on macOS, so nothing is installed locally.
        # Defined (returning empty) so OS-compatibility import is paired with
        # ImportInstalledGames, matching the setup used by working plugins (Humble).
        return []

    async def get_os_compatibility(self, game_id, context):
        # Amazon Games titles are Windows binaries.
        return OSCompatibility.Windows


def main():
    create_and_run_plugin(AmazonPlugin, sys.argv)


if __name__ == "__main__":
    main()
