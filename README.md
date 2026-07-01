# Amazon Games — GOG Galaxy integration (macOS)

*🇬🇧 English first · 🇫🇷 version française plus bas*

Syncs your **Amazon Games library** into GOG Galaxy on macOS, using Amazon's web
API (no native Amazon client exists on Mac). Inspired by
[Nile](https://github.com/imLinguin/nile) (Heroic's Amazon backend) for the
authentication flow and the library API, and by
[Rall3n/galaxy-integration-amazon](https://github.com/Rall3n/galaxy-integration-amazon)
for the GOG patterns.

## What it does / doesn't

| Feature | macOS |
|---|---|
| Amazon account login (OAuth2 + PKCE) | ✅ |
| Owned-games list + titles | ✅ |
| OS-compatibility (Windows) badge | ✅ |
| Achievements | ❌ — Amazon exposes no public achievements API |
| Playtime | ❌ — same, no public API |
| Installed games / launch / install / uninstall | ❌ — needs the Amazon Games client (Windows only) |

> Games appear as "owned". They are Windows binaries: not installable/launchable
> from a Mac, which is expected.

## ⚠️ Critical detail: numeric `user_id`

Before any import, GOG Galaxy "links" the account through its backend
`external-accounts.gog.com/.../platform_login_sessions/amazon`. **That backend
returns HTTP 500 if the `user_id` the plugin returns is not purely numeric.**
Amazon's raw id is `amzn1.account.XXXX` (with dots) → linking fails silently →
the import never starts → the integration shows "Connected" for ~2 s then flips
back to "Not connected" (no error in the plugin log; the cause is only visible in
`/Users/Shared/GOG.com/Galaxy/Logs/GalaxyClient.log`: `Failed linking accounts` /
`Importation cannot start, as Platform 'amazon' was not linked`).

The plugin therefore exposes a **stable numeric `user_id`** derived from the
Amazon id (`amazon_auth.py` → `register_device`). Every platform that works
(Steam, PSN, Xbox, Humble) uses numeric ids — **do not revert to the raw Amazon id.**

## Install

1. Download `amazon-galaxy-plugin.zip` from the
   [Releases page](https://github.com/8ctet/galaxy-integration-amazon-macos/releases).
2. Unzip it into the GOG Galaxy plugins folder (the archive already contains the
   `amazon_<guid>/` folder):
   ```
   ~/Library/Application Support/GOG.com/Galaxy/plugins/installed/
   ```
3. Quit and relaunch GOG Galaxy, then **Connect → Amazon** and sign in. Your
   library appears in the library view.

## Troubleshooting

- **Plugin logs**: `~/Library/Application Support/GOG.com/Galaxy/Logs/plugin-amazon-*.log`
  (tokens are never written there). The account-linking cause, if any, is in the
  client log `/Users/Shared/GOG.com/Galaxy/Logs/GalaxyClient.log`.
- **TLS / certificates**: Galaxy's bundled Python has no system CA bundle
  (otherwise `CERTIFICATE_VERIFY_FAILED`). The plugin ships `certifi` and uses it
  by default.
- **Library 401**: the plugin refreshes the token and retries once; the header
  used is `x-amzn-token` (not `Authorization: bearer`).
- **Non-US account (e.g. FR)**: `marketPlaceId` is US (`ATVPDKIKX0DER`) like Nile;
  entitlements are account-scoped, so the full library still loads.
- **Private Amazon endpoints**: they can change without notice.

## Architecture

```
src/
  plugin.py         AmazonPlugin(Plugin) — GOG glue (auth, owned games, OS compat)
  amazon_auth.py    OAuth2 + PKCE: register / refresh / token state
  amazon_library.py Entitlements + pagination
  http_client.py    Async HTTP client over urllib (zero native deps)
  consts.py         Amazon constants & endpoints
  version.py
tools/standalone_check.py   Off-Galaxy test harness
build.py                    Vendors galaxy/ + certifi/ + writes manifest + installs
```

**Key choice**: no native dependencies. The `galaxy.api.plugin` import chain is
100 % stdlib (`aiohttp` is only used by `galaxy/http.py`, which is never
imported), and the HTTP client relies on `urllib`. The plugin therefore runs
as-is on the Python 3.7 / x86_64 that GOG Galaxy bundles, with no wheel compilation.

## Credits

- API: [gogcom/galaxy-integrations-python-api](https://github.com/gogcom/galaxy-integrations-python-api)
- Amazon flow: [imLinguin/nile](https://github.com/imLinguin/nile)
- Original Windows plugin: [Rall3n/galaxy-integration-amazon](https://github.com/Rall3n/galaxy-integration-amazon)

## License

[MIT](LICENSE) © 2026 8ctet. The Amazon protocol details come from the community
reverse-engineering in [Nile](https://github.com/imLinguin/nile).

---

# 🇫🇷 Amazon Games — intégration GOG Galaxy (macOS)

Synchronise votre **ludothèque Amazon Games** dans GOG Galaxy sur macOS, via les
API web d'Amazon (aucun client Amazon natif n'existe sur Mac). Inspiré de
[Nile](https://github.com/imLinguin/nile) (backend Amazon de Heroic) pour le flux
d'authentification et l'API ludothèque, et de
[Rall3n/galaxy-integration-amazon](https://github.com/Rall3n/galaxy-integration-amazon)
pour les patterns GOG.

## Ce que ça fait / ne fait pas

| Fonction | macOS |
|---|---|
| Connexion au compte Amazon (OAuth2 + PKCE) | ✅ |
| Liste des jeux possédés + titres | ✅ |
| Compatibilité OS (Windows) affichée | ✅ |
| Succès | ❌ — Amazon n'expose aucune API publique de succès |
| Temps de jeu | ❌ — idem, aucune API publique |
| Jeux installés / lancer / installer / désinstaller | ❌ — nécessite le client Amazon Games (Windows uniquement) |

> Les jeux apparaissent comme « possédés ». Ce sont des binaires Windows : non
> installables/lançables depuis un Mac, ce qui est normal.

## ⚠️ Détail critique : `user_id` numérique

Avant tout import, GOG Galaxy « lie » le compte via son backend
`external-accounts.gog.com/.../platform_login_sessions/amazon`. **Ce backend renvoie
une erreur 500 si le `user_id` renvoyé par le plugin n'est pas purement numérique.**
L'ID Amazon brut est `amzn1.account.XXXX` (avec des points) → la liaison échoue
silencieusement → l'import ne démarre jamais → l'intégration affiche « Connecté »
~2 s puis repasse « Non connecté » (aucune erreur dans le log du plugin ; la cause
n'est visible que dans `/Users/Shared/GOG.com/Galaxy/Logs/GalaxyClient.log` :
`Failed linking accounts` / `Importation cannot start, as Platform 'amazon' was not linked`).

Le plugin expose donc un `user_id` **numérique stable** dérivé de l'ID Amazon
(`amazon_auth.py` → `register_device`). Toutes les plateformes qui fonctionnent
(Steam, PSN, Xbox, Humble) utilisent des `user_id` numériques — **ne pas revenir à
l'ID Amazon brut.**

## Installer

1. Téléchargez `amazon-galaxy-plugin.zip` depuis la
   [page Releases](https://github.com/8ctet/galaxy-integration-amazon-macos/releases).
2. Dézippez l'archive dans le dossier des plugins de GOG Galaxy (l'archive contient
   déjà le dossier `amazon_<guid>/`) :
   ```
   ~/Library/Application Support/GOG.com/Galaxy/plugins/installed/
   ```
3. Quittez puis relancez GOG Galaxy → **Connect → Amazon** → connectez-vous. Votre
   ludothèque apparaît dans la bibliothèque.

## Dépannage

- **Logs du plugin** : `~/Library/Application Support/GOG.com/Galaxy/Logs/plugin-amazon-*.log`
  (les tokens n'y sont jamais écrits). La cause d'un échec de liaison de compte
  est dans le log client `/Users/Shared/GOG.com/Galaxy/Logs/GalaxyClient.log`.
- **TLS / certificats** : le Python embarqué par Galaxy n'a pas de bundle CA
  système (sinon `CERTIFICATE_VERIFY_FAILED`). Le plugin embarque `certifi` et
  l'utilise par défaut.
- **401 sur la ludothèque** : le plugin rafraîchit le token puis réessaie une fois ;
  l'en-tête utilisé est `x-amzn-token` (et non `Authorization: bearer`).
- **Compte non-US (ex. FR)** : le `marketPlaceId` est l'US (`ATVPDKIKX0DER`) comme
  Nile ; les entitlements étant liés au compte, la ludothèque complète remonte.
- **Endpoints Amazon privés** : ils peuvent changer sans préavis.

## Architecture

```
src/
  plugin.py         AmazonPlugin(Plugin) — colle GOG (auth, owned games, OS compat)
  amazon_auth.py    OAuth2 + PKCE : register / refresh / état des tokens
  amazon_library.py Entitlements + pagination
  http_client.py    Client HTTP async basé sur urllib (zéro dépendance native)
  consts.py         Constantes & endpoints Amazon
  version.py
tools/standalone_check.py   Harnais de test hors-Galaxy
build.py                    Vendoring de galaxy/ + certifi/ + manifest + install
```

**Choix clé** : aucune dépendance native. La chaîne d'import de `galaxy.api.plugin`
est 100 % stdlib (`aiohttp` n'est utilisé que par `galaxy/http.py`, jamais importé),
et le client HTTP s'appuie sur `urllib`. Le plugin tourne donc tel quel sur le
Python 3.7 / x86_64 embarqué par Galaxy, sans compilation de wheels.

## Crédits

- API : [gogcom/galaxy-integrations-python-api](https://github.com/gogcom/galaxy-integrations-python-api)
- Flux Amazon : [imLinguin/nile](https://github.com/imLinguin/nile)
- Plugin Windows original : [Rall3n/galaxy-integration-amazon](https://github.com/Rall3n/galaxy-integration-amazon)

## Licence

[MIT](LICENSE) © 2026 8ctet. Les détails du protocole Amazon proviennent du
reverse-engineering communautaire de [Nile](https://github.com/imLinguin/nile).
