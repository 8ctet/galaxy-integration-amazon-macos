#!/usr/bin/env python3
"""Exercise the Amazon auth + entitlements paths WITHOUT GOG Galaxy.

Run it with Galaxy's bundled Python 3.7 to match the real runtime exactly:

  "/Applications/GOG Galaxy.app/Contents/Frameworks/Python.framework/Versions/3.7/bin/python3" \
      tools/standalone_check.py

Login mode (default):
  1. Prints the Amazon sign-in URL — open it in a browser and log in.
  2. After login you land on https://www.amazon.com/?...openid.oa2.authorization_code=...
     Copy that final URL and paste it back here.
  3. The script registers the device, fetches entitlements and prints a summary.
  4. Credentials are saved to tools/.creds.json for --refresh.

Refresh mode:
  python3 tools/standalone_check.py --refresh
"""

import asyncio
import json
import os
import sys
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from amazon_auth import AmazonAuthClient  # noqa: E402
from amazon_library import AmazonLibraryClient  # noqa: E402
from http_client import HttpClient  # noqa: E402

CREDS_FILE = os.path.join(os.path.dirname(__file__), ".creds.json")


async def do_login():
    http = HttpClient()
    auth = AmazonAuthClient(http)
    url = auth.prepare_login()
    print("\n1) Open this URL in your browser and log in to Amazon:\n")
    print(url)
    print(
        "\n2) After login you are redirected to https://www.amazon.com/?... "
        "Paste that FULL url below.\n"
    )
    redirect = input("Redirect URL: ").strip()
    code = parse_qs(urlsplit(redirect).query).get(
        "openid.oa2.authorization_code", [None]
    )[0]
    if not code:
        print("ERROR: no openid.oa2.authorization_code found in that URL.")
        return 1

    print("\nRegistering device...")
    creds = await auth.register_device(code)
    with open(CREDS_FILE, "w") as fh:
        json.dump(creds, fh)
    print("Registered as user_id=%s name=%s" % (auth.user_id, auth.user_name))

    await fetch_and_print(http, auth)
    print("\nCredentials saved to %s (use --refresh to test token refresh)." % CREDS_FILE)
    return 0


async def do_refresh():
    if not os.path.exists(CREDS_FILE):
        print("No saved credentials. Run without --refresh first.")
        return 1
    http = HttpClient()
    auth = AmazonAuthClient(http)
    with open(CREDS_FILE) as fh:
        auth.restore(json.load(fh))
    print("Forcing token refresh...")
    creds = await auth.refresh()
    with open(CREDS_FILE, "w") as fh:
        json.dump(creds, fh)
    print("Refreshed. expires_in=%s" % auth.expires_in)
    await fetch_and_print(http, auth)
    return 0


async def fetch_and_print(http, auth):
    lib = AmazonLibraryClient(http)
    ents = await lib.get_entitlements(auth.access_token, auth.hardware_serial)
    print("\nOwned games: %d" % len(ents))
    for ent in ents[:15]:
        product = ent.get("product") or {}
        print("  - %s  [%s]" % (product.get("title"), product.get("id")))
    if len(ents) > 15:
        print("  ... and %d more" % (len(ents) - 15))


def main():
    refresh = "--refresh" in sys.argv[1:]
    coro = do_refresh() if refresh else do_login()
    sys.exit(asyncio.get_event_loop().run_until_complete(coro))


if __name__ == "__main__":
    main()
