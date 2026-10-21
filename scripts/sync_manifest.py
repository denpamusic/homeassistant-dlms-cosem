"""Synchronize manifest.json and hacs.json from pyproject.toml."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import tomllib
from typing import Any

from packaging.requirements import Requirement

ROOT_DIR = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = ROOT_DIR / "pyproject.toml"
MANIFEST_PATH = ROOT_DIR / "custom_components" / "dlms_cosem" / "manifest.json"
HACS_PATH = ROOT_DIR / "hacs.json"


def _extract_ha_version(req: Requirement) -> str | None:
    """Extract minimum Home Assistant version from Requirement."""
    for spec in req.specifier:
        if spec.operator in (">=", "==", "~="):
            return spec.version
    return None


def _load_pyproject_data() -> tuple[str, list[str], str | None]:
    """Load version, requirements and HA version from pyproject.toml."""
    with PYPROJECT_PATH.open("rb") as f:
        pyproject = tomllib.load(f)

    project = pyproject.get("project", {})
    version: str = project.get("version", "")
    deps: list[str] = project.get("dependencies", [])

    requirements: list[str] = []
    ha_version: str | None = None

    for dep in deps:
        req = Requirement(dep)
        if req.name.lower() == "homeassistant":
            ha_version = _extract_ha_version(req)
        else:
            requirements.append(dep)

    return version, sorted(requirements), ha_version


def _sync_manifest(version: str, requirements: list[str], check: bool) -> bool:
    """Synchronize manifest.json. Return True if file differs."""
    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        manifest_data: dict[str, Any] = json.load(f)

    changed = False
    if manifest_data.get("version") != version:
        manifest_data["version"] = version
        changed = True

    if manifest_data.get("requirements") != requirements:
        manifest_data["requirements"] = requirements
        changed = True

    if not changed:
        return False

    if not check:
        with MANIFEST_PATH.open("w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
            f.write("\n")

    return True


def _sync_hacs(ha_version: str | None, check: bool) -> bool:
    """Synchronize hacs.json. Return True if file differs."""
    if not ha_version:
        return False

    with HACS_PATH.open("r", encoding="utf-8") as f:
        hacs_data: dict[str, Any] = json.load(f)

    if hacs_data.get("homeassistant") == ha_version:
        return False

    hacs_data["homeassistant"] = ha_version

    if not check:
        with HACS_PATH.open("w", encoding="utf-8") as f:
            json.dump(hacs_data, f, indent=4)
            f.write("\n")

    return True


def main() -> int:
    """Run the synchronization script."""
    parser = argparse.ArgumentParser(
        description="Sync manifest.json and hacs.json from pyproject.toml"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check if files are synchronized without modifying them.",
    )
    args = parser.parse_args()

    version, requirements, ha_version = _load_pyproject_data()

    manifest_changed = _sync_manifest(version, requirements, args.check)
    hacs_changed = _sync_hacs(ha_version, args.check)

    if args.check:
        if manifest_changed or hacs_changed:
            if manifest_changed:
                sys.stdout.write(
                    f"ERROR: {MANIFEST_PATH.relative_to(ROOT_DIR)} is out of sync"
                    " with pyproject.toml\n"
                )
            if hacs_changed:
                sys.stdout.write(
                    f"ERROR: {HACS_PATH.relative_to(ROOT_DIR)} is out of sync"
                    " with pyproject.toml\n"
                )
            sys.stdout.write("Run 'python scripts/sync_manifest.py' to synchronize.\n")
            return 1
        sys.stdout.write("manifest.json and hacs.json are up to date.\n")
        return 0

    if manifest_changed:
        sys.stdout.write(f"Updated {MANIFEST_PATH.relative_to(ROOT_DIR)}\n")
    if hacs_changed:
        sys.stdout.write(f"Updated {HACS_PATH.relative_to(ROOT_DIR)}\n")
    if not manifest_changed and not hacs_changed:
        sys.stdout.write("manifest.json and hacs.json are already up to date.\n")

    return 0


if __name__ == "__main__":
    sys.exit(main())
