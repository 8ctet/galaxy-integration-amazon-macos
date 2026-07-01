# Amazon Games — intégration GOG Galaxy (macOS)

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

## Pré-requis

- macOS avec **GOG Galaxy 2.0** installé (embarque son propre Python 3.7 x86_64).
- Un compte Amazon possédant des jeux Amazon Games / Prime Gaming.

## Construire & installer

```bash
cd "Plugin GOG Amazon"
PY37="/Applications/GOG Galaxy.app/Contents/Frameworks/Python.framework/Versions/3.7/bin/python3.7"

# Construit dans dist/amazon_<guid>/ (vendorise l'API GOG v0.69 depuis un plugin déjà installé)
"$PY37" build.py

# …puis installe directement dans GOG Galaxy :
"$PY37" build.py --install
```

Quittez puis relancez GOG Galaxy → **Connect → Amazon** → connectez-vous dans la
fenêtre Amazon. Votre ludothèque apparaît dans la bibliothèque.

## Tester sans Galaxy (recommandé en premier)

Valide l'authentification et la récupération de la ludothèque, avec une sortie
lisible et facile à déboguer :

```bash
"$PY37" tools/standalone_check.py
# 1) ouvrez l'URL affichée dans un navigateur, connectez-vous
# 2) collez l'URL https://www.amazon.com/?...openid.oa2.authorization_code=... finale
# 3) le script affiche le nombre de jeux + les premiers titres
"$PY37" tools/standalone_check.py --refresh   # teste le rafraîchissement du token
```

## Dépannage

- **Logs du plugin** : `~/Library/Application Support/GOG.com/Galaxy/Logs/plugin-amazon-*.log`
  (les tokens n'y sont jamais écrits).
- **TLS / certificats** : le Python embarqué par Galaxy n'a pas de bundle CA
  système (sinon : `CERTIFICATE_VERIFY_FAILED`). Le plugin embarque donc `certifi`
  (vendorisé automatiquement par `build.py`, comme les autres plugins Galaxy) et
  l'utilise par défaut. Si le build affiche « WARNING: no certifi found »,
  lance `pip install certifi --target dist/amazon_<guid>`.
- **401 sur la ludothèque** : le plugin rafraîchit le token puis réessaie une fois ;
  l'en-tête utilisé est `x-amzn-token` (et non `Authorization: bearer`).
- **Compte non-US (ex. FR)** : le `marketPlaceId` est l'US (`ATVPDKIKX0DER`) comme
  Nile ; les entitlements étant liés au compte, la ludothèque complète remonte
  normalement. Si un jeu manque, ouvrez un ticket.
- **Endpoints Amazon privés** : ils peuvent changer sans préavis. Lancez d'abord
  `tools/standalone_check.py` pour confirmer.

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
build.py                    Vendoring de galaxy/ + manifest + install
```

**Choix clé** : aucune dépendance native. La chaîne d'import de `galaxy.api.plugin`
est 100 % stdlib (`aiohttp` n'est utilisé que par `galaxy/http.py`, jamais importé),
et le client HTTP s'appuie sur `urllib`. Le plugin tourne donc tel quel sur le
Python 3.7 / x86_64 embarqué par Galaxy, sans compilation de wheels.

## Crédits

- API : [gogcom/galaxy-integrations-python-api](https://github.com/gogcom/galaxy-integrations-python-api)
- Flux Amazon : [imLinguin/nile](https://github.com/imLinguin/nile)
- Plugin Windows original : [Rall3n/galaxy-integration-amazon](https://github.com/Rall3n/galaxy-integration-amazon)

## Publier sur GitHub

1. Éditez `GITHUB_REPO` en haut de `build.py` (mettez votre `owner/repo`), puis
   relancez `build.py` — il régénère `manifest.json` (`url` + `update_url`) et
   `current_version.json`.
2. Créez le dépôt et poussez :
   ```bash
   gh repo create <owner>/galaxy-integration-amazon-macos --public --source=. --push
   # ou manuellement :
   git remote add origin https://github.com/<owner>/galaxy-integration-amazon-macos.git
   git push -u origin main
   ```
3. **Mise à jour auto (optionnel)** : `build.py --zip` produit
   `dist/amazon-galaxy-plugin.zip`. Créez une release GitHub taguée comme
   `PLUGIN_VERSION` (ex. `0.1.0`) et attachez-y ce zip. Galaxy lit
   `current_version.json` via `update_url` et proposera la mise à jour.

> `dist/` et les fichiers de tokens de test sont ignorés par git (`.gitignore`) —
> ne committez jamais `tools/.creds.json` / `.amzn_*.json`.

## Licence

[MIT](LICENSE) © 2026 8ctet. Les détails du protocole Amazon proviennent du
reverse-engineering communautaire de [Nile](https://github.com/imLinguin/nile).
