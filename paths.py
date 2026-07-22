"""
paths.py — central application-data directory resolution for Paramodus.

All persistent local data lives under a single platform-appropriate
application-data directory:

  Windows:  %APPDATA%\\Paramodus          (C:\\Users\\<you>\\AppData\\Roaming\\Paramodus)
  macOS:    ~/Library/Application Support/Paramodus
  Linux:    ${XDG_DATA_HOME:-~/.local/share}/Paramodus

This replaces the legacy hardcoded ~/.myapp location.  On first run, if the
legacy ~/.myapp directory exists and the new location is empty, its contents
(model files, LanceDB vector store, SQLite history/memory, llama-server log)
are moved into the new location so existing users keep their data.

Centralizing this here means database.py, agents/workspace_agent.py, and
local_model/manager.py all agree on a single path — no more duplicated
os.path.expanduser("~/.myapp") constants drifting out of sync.
"""

import os
import shutil
import sys

APP_DIR_NAME = "Paramodus"
LEGACY_DIR_NAME = ".myapp"


def _platform_app_data_dir() -> str:
    """Return the platform-conventional app-data dir for Paramodus."""
    if sys.platform == "win32":
        # %APPDATA% = C:\\Users\\<you>\\AppData\\Roaming
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        return os.path.join(base, APP_DIR_NAME)
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~"), "Library", "Application Support", APP_DIR_NAME
        )
    # Linux / other Unix — follow XDG
    base = os.environ.get("XDG_DATA_HOME") or os.path.join(
        os.path.expanduser("~"), ".local", "share"
    )
    return os.path.join(base, APP_DIR_NAME)


def _legacy_dir() -> str:
    return os.path.join(os.path.expanduser("~"), LEGACY_DIR_NAME)


def _is_empty(path: str) -> bool:
    return not os.listdir(path)


def _migrate(src: str, dst: str) -> None:
    """
    Move the contents of the legacy ~/.myapp dir into the new app-data dir.

    Per-entry try/except so one locked file (rare, e.g. an open DB on a
    crashed prior run) doesn't abort the whole migration.
    """
    for entry in os.listdir(src):
        s = os.path.join(src, entry)
        d = os.path.join(dst, entry)
        if os.path.exists(d):
            # Already present in destination — don't overwrite.
            continue
        try:
            shutil.move(s, d)
        except OSError as exc:
            print(f"[paths] Could not migrate {s}: {exc}")
    # Remove the legacy dir if it's now empty.
    try:
        if _is_empty(src):
            os.rmdir(src)
    except OSError:
        pass


def get_app_data_dir() -> str:
    """
    Return the application data directory, creating it if needed.

    On first call after an upgrade from the legacy ~/.myapp layout, the
    legacy contents are migrated into the new location (only if the new
    location is empty — existing new-layout installs are left untouched).
    """
    new_dir = _platform_app_data_dir()
    legacy = _legacy_dir()

    try:
        os.makedirs(new_dir, exist_ok=True)
    except OSError:
        # Extremely rare (e.g. %APPDATA% unset and ~ unwritable) — fall back
        # to the legacy path so the app still runs instead of crashing.
        return legacy

    # One-time migration from ~/.myapp -> new location
    try:
        if os.path.isdir(legacy) and not _is_empty(legacy) and _is_empty(new_dir):
            _migrate(legacy, new_dir)
    except OSError as exc:
        print(f"[paths] Migration from {legacy} failed: {exc}")

    return new_dir
