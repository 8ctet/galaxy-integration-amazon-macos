#!/usr/bin/env python3
"""Assemble the installable GOG Galaxy plugin folder.

Steps:
  1. Compute a stable plugin GUID.
  2. Copy the plugin sources from src/.
  3. Vendor the GOG Galaxy API (the pure-Python `galaxy/` package) by copying it
     from an already-installed FriendsOfGalaxy plugin (v0.69, the version your
     Galaxy client runs). Override with --galaxy-src /path/to/galaxy.
  4. Write manifest.json.
  5. With --install, copy the result into the macOS plugins directory.

Usage:
  python3 build.py                 # build into dist/amazon_<guid>/
  python3 build.py --install       # build, then install into Galaxy
  python3 build.py --galaxy-src ~/path/to/some_plugin/galaxy
"""

import argparse
import os
import shutil
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(ROOT, "src")
DIST = os.path.join(ROOT, "dist")

# Fixed unique identifier for this integration. Do NOT change once published —
# it is the plugin's identity in GOG Galaxy (changing it forces a reconnect).
PLUGIN_GUID = "e138bb52-853f-3d56-b4eb-a41178438c56"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DIRNAME = "amazon_" + PLUGIN_GUID

# GitHub "owner/repo" — EDIT THIS to your repository before publishing. Used for the
# manifest url and for GOG's auto-update check (update_url -> current_version.json).
GITHUB_REPO = "8ctet/galaxy-integration-amazon-macos"

GALAXY_PLUGINS_DIR = os.path.expanduser(
    "~/Library/Application Support/GOG.com/Galaxy/plugins/installed"
)

MANIFEST = {
    "name": "Amazon Games",
    "platform": "amazon",
    "guid": PLUGIN_GUID,
    "version": PLUGIN_VERSION,
    "description": "Synchronise votre ludothèque Amazon Games dans GOG Galaxy (macOS).",
    "author": "8ctet",
    "url": "https://github.com/" + GITHUB_REPO,
    "update_url": "https://raw.githubusercontent.com/" + GITHUB_REPO + "/main/current_version.json",
    "script": "plugin.py",
}

_IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo", "*.dist-info", "tests")


def _detect_version(plugin_dir):
    """Return the galaxy.plugin.api version of an installed plugin, or None."""
    import glob
    import re

    for info in glob.glob(os.path.join(plugin_dir, "galaxy.plugin.api-*.dist-info")):
        m = re.search(r"galaxy\.plugin\.api-([0-9][0-9.]*)\.dist-info", info)
        if m:
            return tuple(int(p) for p in m.group(1).split("."))
    return None


def find_certifi_source():
    """Locate a vendored certifi package in an installed plugin (e.g. Steam).

    Galaxy's bundled Python has no usable system CA bundle, so the plugin must
    ship certifi or TLS verification fails (CERTIFICATE_VERIFY_FAILED).
    """
    if not os.path.isdir(GALAXY_PLUGINS_DIR):
        return None
    for entry in sorted(os.listdir(GALAXY_PLUGINS_DIR)):
        cand = os.path.join(GALAXY_PLUGINS_DIR, entry, "certifi")
        if os.path.isfile(os.path.join(cand, "cacert.pem")):
            return cand
    return None


def find_galaxy_source(override):
    if override:
        if not os.path.isfile(os.path.join(override, "api", "plugin.py")):
            sys.exit("ERROR: --galaxy-src %r has no api/plugin.py" % override)
        return override
    if not os.path.isdir(GALAXY_PLUGINS_DIR):
        sys.exit(
            "ERROR: %s not found. Pass --galaxy-src or `pip install "
            "galaxy.plugin.api==0.69.0 --target <dir>` and point at <dir>/galaxy."
            % GALAXY_PLUGINS_DIR
        )
    versioned = []  # (version_tuple, galaxy_dir)
    unversioned = []
    for entry in sorted(os.listdir(GALAXY_PLUGINS_DIR)):
        plugin_dir = os.path.join(GALAXY_PLUGINS_DIR, entry)
        cand = os.path.join(plugin_dir, "galaxy")
        if not os.path.isfile(os.path.join(cand, "api", "plugin.py")):
            continue
        ver = _detect_version(plugin_dir)
        (versioned if ver else unversioned).append((ver, cand))
    # Prefer the highest known version (the user's client ships v0.69); fall back
    # to any galaxy/ package if none carry a dist-info marker.
    if versioned:
        ver, cand = max(versioned, key=lambda x: x[0])
        print("Detected galaxy.plugin.api v%s" % ".".join(map(str, ver)))
        return cand
    if unversioned:
        return unversioned[0][1]
    sys.exit(
        "ERROR: no installed plugin with a galaxy/ package found. "
        "Pass --galaxy-src /path/to/galaxy."
    )


def build(galaxy_src_override):
    out = os.path.join(DIST, PLUGIN_DIRNAME)
    if os.path.exists(out):
        shutil.rmtree(out)
    os.makedirs(out)

    # Plugin sources.
    for name in os.listdir(SRC):
        if name.endswith(".py"):
            shutil.copy2(os.path.join(SRC, name), os.path.join(out, name))

    # Vendored GOG API.
    galaxy_src = find_galaxy_source(galaxy_src_override)
    shutil.copytree(galaxy_src, os.path.join(out, "galaxy"), ignore=_IGNORE)
    print("Vendored galaxy/ from: %s" % galaxy_src)

    # Vendored certifi (required: Galaxy's Python has no usable system CA bundle).
    certifi_src = find_certifi_source()
    if certifi_src:
        shutil.copytree(certifi_src, os.path.join(out, "certifi"), ignore=_IGNORE)
        print("Vendored certifi/ from: %s" % certifi_src)
    else:
        print(
            "WARNING: no certifi found in installed plugins. TLS will fail under "
            "Galaxy. Run: pip install certifi --target '%s'" % out
        )

    # Manifest.
    import json

    with open(os.path.join(out, "manifest.json"), "w") as fh:
        json.dump(MANIFEST, fh, indent=4, ensure_ascii=False)

    # Ship the README inside the plugin folder too (matches other Galaxy plugins).
    readme = os.path.join(ROOT, "README.md")
    if os.path.isfile(readme):
        shutil.copy2(readme, os.path.join(out, "README.md"))

    # Auto-update descriptor kept at the repo root (GOG fetches it via update_url).
    current_version = {
        "tag_name": PLUGIN_VERSION,
        "assets": [{
            "name": "amazon-galaxy-plugin.zip",
            "browser_download_url": "https://github.com/%s/releases/download/%s/amazon-galaxy-plugin.zip"
            % (GITHUB_REPO, PLUGIN_VERSION),
        }],
    }
    with open(os.path.join(ROOT, "current_version.json"), "w") as fh:
        json.dump(current_version, fh, indent=4)

    print("Built: %s" % out)
    return out


def install(built_dir):
    dest = os.path.join(GALAXY_PLUGINS_DIR, PLUGIN_DIRNAME)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.copytree(built_dir, dest)
    print("Installed: %s" % dest)
    print("Now quit & relaunch GOG Galaxy, then Connect -> Amazon.")


def make_zip():
    """Zip the built plugin folder for upload as a GitHub release asset."""
    archive = shutil.make_archive(
        os.path.join(DIST, "amazon-galaxy-plugin"), "zip",
        root_dir=DIST, base_dir=PLUGIN_DIRNAME,
    )
    print("Zipped: %s" % archive)
    return archive


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--install", action="store_true", help="install into GOG Galaxy")
    ap.add_argument("--zip", action="store_true", help="zip the built plugin for a GitHub release")
    ap.add_argument("--galaxy-src", help="path to a galaxy/ package to vendor")
    args = ap.parse_args()
    built = build(args.galaxy_src)
    if args.install:
        install(built)
    if args.zip:
        make_zip()


if __name__ == "__main__":
    main()
