"""Amazon Games constants and endpoints.

Values mirror the Amazon Games launcher ("Sonic"/"AGSLauncher") as reverse
engineered by the Nile project (https://github.com/imLinguin/nile). The device
profile is intentionally Windows-flavoured: the entitlements service authorises
against the AGS-launcher device type, so these must not be "corrected" to macOS.
"""

# Device / app identity (must match what the entitlements service expects).
DEVICE_TYPE = "A2UMVHOX7UP4V7"
APP_NAME = "AGSLauncher for Windows"
APP_VERSION = "1.0.0"
DEVICE_MODEL = "Windows"
OS_VERSION = "10.0.19044.0"

# US marketplace. Entitlements are account-global, so this returns the full
# library regardless of the account's home marketplace (see README "known risks").
MARKETPLACE_ID = "ATVPDKIKX0DER"

# Fixed key id used by the AGS launcher when calling the distribution service.
HARDWARE_KEY_ID = "d5dc8b8b-86c8-4fc4-ae93-18c0def5314d"

# User-Agent the AGS launcher sends to the SDS / distribution endpoints.
SDS_USER_AGENT = "com.amazon.agslauncher.win/3.0.9202.1"

# --- Endpoints -------------------------------------------------------------
AMAZON_API = "https://api.amazon.com"
AMAZON_SIGNIN = "https://amazon.com/ap/signin"
AMAZON_REGISTER = AMAZON_API + "/auth/register"
AMAZON_TOKEN = AMAZON_API + "/auth/token"

ENTITLEMENTS_URL = "https://gaming.amazon.com/api/distribution/entitlements"
ENTITLEMENTS_TARGET = (
    "com.amazon.animusdistributionservice.entitlement"
    ".AnimusEntitlementsService.GetEntitlements"
)

# OpenID 2.0 assoc handle / page id used by the launcher login.
ASSOC_HANDLE = "amzn_sonic_games_launcher"
# Where Amazon redirects after a successful login (carries the auth code).
RETURN_TO = "https://www.amazon.com"
