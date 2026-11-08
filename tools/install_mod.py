#!/usr/bin/env python3
"""Copy the mod into the Victoria 3 user mod folder and create the launcher .mod.

The launcher discovers a local mod through a `.mod` file in the user's mod
folder whose `path` points at the mod directory. Copying only the repository
folder is not enough on its own, so this tool writes both parts.

Usage:
    python3 tools/install_mod.py --dry-run
    python3 tools/install_mod.py
    python3 tools/install_mod.py --user-dir "/path/to/Paradox Interactive/Victoria 3"
"""
from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MOD_NAME = "Smart Government Advisor"
IGNORE = shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store")


def user_data_candidates() -> list[Path]:
    result: list[Path] = []
    env = os.environ.get("VICTORIA3_USER_DIR")
    if env:
        result.append(Path(env).expanduser())
    home = Path.home()
    result.extend(
        [
            home / ".local" / "share" / "Paradox Interactive" / "Victoria 3",
            home
            / ".config"
            / "hydralauncher"
            / "wine-prefixes",
        ]
    )
    # Expand every Hydra/Wine prefix.
    prefixes = home / ".config" / "hydralauncher" / "wine-prefixes"
    if prefixes.is_dir():
        for prefix in prefixes.iterdir():
            result.append(
                prefix
                / "drive_c"
                / "users"
                / "steamuser"
                / "Documents"
                / "Paradox Interactive"
                / "Victoria 3"
            )
    result.append(
        home
        / "Documents"
        / "Paradox Interactive"
        / "Victoria 3"
    )
    return result


def resolve_user_dir(value: str | None) -> Path:
    if value:
        path = Path(value).expanduser()
        if (path / "mod").is_dir() or path.is_dir():
            return path
        raise SystemExit(f"{path} does not exist.")
    for candidate in user_data_candidates():
        if (candidate / "mod").is_dir():
            return candidate
    raise SystemExit(
        "Could not find the Victoria 3 user folder. Pass --user-dir "
        "'/path/to/Paradox Interactive/Victoria 3'."
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-dir", default=None)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing installed copy (the source is never deleted).",
    )
    args = parser.parse_args()

    user_dir = resolve_user_dir(args.user_dir)
    mod_root = user_dir / "mod"
    target = mod_root / MOD_NAME
    descriptor = mod_root / f"{MOD_NAME}.mod"
    content_load = user_dir / "content_load.json"

    print(f"User data: {user_dir}")
    print(f"Mod folder: {target}")
    print(f"Launcher descriptor: {descriptor}")
    if content_load.is_file():
        print(f"Back up before activating: {content_load}")
    if args.dry_run:
        return 0

    staging = mod_root / f".{MOD_NAME}.staging"
    previous = mod_root / f".{MOD_NAME}.previous"
    descriptor_staging = mod_root / f".{MOD_NAME}.mod.staging"
    if staging.exists() or previous.exists() or descriptor_staging.exists():
        raise SystemExit(
            f"Temporary install path already exists under {mod_root}; "
            "remove it after confirming no install is running."
        )

    if target.exists():
        if not args.force:
            raise SystemExit(
                f"{target} already exists. Re-run with --force to replace it."
            )

    descriptor_text = (
        "version=\"1.0.0\"\n"
        "tags={\n\t\"Utilities\"\n\t\"Politics\"\n}\n"
        f"name=\"{MOD_NAME}\"\n"
        "supported_version=\"1.15.*\"\n"
        f"path=\"mod/{MOD_NAME}\"\n"
    )
    try:
        shutil.copytree(ROOT, staging, ignore=IGNORE)
        descriptor_staging.write_text(descriptor_text, encoding="utf-8")
        if target.exists():
            target.rename(previous)
        staging.rename(target)
        descriptor_staging.replace(descriptor)
    except Exception:
        if target.exists() and not previous.exists():
            shutil.rmtree(target)
        if previous.exists() and not target.exists():
            previous.rename(target)
        raise
    finally:
        if staging.exists():
            shutil.rmtree(staging)
        if descriptor_staging.exists():
            descriptor_staging.unlink()
    if previous.exists():
        shutil.rmtree(previous)
    print("Installed. Activate the mod in the launcher.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
