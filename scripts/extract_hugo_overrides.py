#!/usr/bin/env python3
"""Extract Hugo theme files to resources for override editing.

This script copies theme files from storage/hugo/themes to
resources/hugo/themes/{theme}/. By default, files are copied as-is
for manual editing. Use --inject to apply tracking and internal-links
injections automatically.

Usage:
    python scripts/extract_hugo_overrides.py                 # Copy as-is
    python scripts/extract_hugo_overrides.py --inject        # Apply injections
    python scripts/extract_hugo_overrides.py --force         # Overwrite existing
    python scripts/extract_hugo_overrides.py --theme stack   # One theme only
"""

import argparse
import shutil
import sys
from pathlib import Path
import time

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from site_automator.hugo import HugoDeployer

# Define which files to extract per theme
THEME_OVERRIDES = {
    "ananke": [
        "layouts/baseof.html",
        "layouts/single.html",
    ],
    "beautifulhugo": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
    "clarity": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
    "mainroad": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
    "paper": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
    "papermod": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
    "stack": [
        "layouts/baseof.html",
        # Stack uses nested partials - override article.html instead of single.html
        "layouts/_partials/article/article.html",
    ],
    "terminal": [
        "layouts/_default/baseof.html",
        "layouts/_default/single.html",
    ],
}


def extract_theme_overrides(
    theme: str,
    storage_dir: Path,
    resources_dir: Path,
    force: bool = False,
    inject: bool = False,
) -> None:
    """Extract theme files for a single theme.

    Args:
        theme: Theme name (e.g., "stack")
        storage_dir: Path to storage/hugo/themes
        resources_dir: Path to resources/hugo/themes
        force: If True, overwrite existing files
        inject: If True, apply injections; otherwise copy as-is
    """
    if theme not in THEME_OVERRIDES:
        print(f"  No override config for theme '{theme}' - skipping")
        return

    theme_storage = storage_dir / theme
    if not theme_storage.exists():
        print(f"  ✗ Theme not found in storage: {theme}")
        return

    theme_resources = resources_dir / theme
    overrides = THEME_OVERRIDES[theme]

    print(f"\n{theme}:")
    print(f"  Source: {theme_storage}")
    print(f"  Target: {theme_resources}")
    print(f"  Mode:   {'inject' if inject else 'copy'}")

    # Create HugoDeployer instance for injection methods (only if needed)
    deployer = HugoDeployer.__new__(HugoDeployer) if inject else None

    for file_path in overrides:
        source_file = theme_storage / file_path
        dest_file = theme_resources / file_path

        # Check if source exists
        if not source_file.exists():
            print(f"  ✗ {file_path} - NOT FOUND in theme")
            continue

        # Check if dest already exists (unless force)
        if dest_file.exists() and not force:
            print(f"  ⊘ {file_path} - exists (use --force to overwrite)")
            continue

        # Create parent directory
        dest_file.parent.mkdir(parents=True, exist_ok=True)

        if inject:
            # Apply injections
            try:
                content = source_file.read_text()
            except Exception as e:
                print(f"  ✗ {file_path} - read error: {e}")
                continue

            patched = content
            if "baseof.html" in file_path:
                try:
                    patched = deployer._inject_tracking_into_baseof(content)  # type: ignore
                    injection_note = "tracking injected"
                except Exception as e:
                    print(f"  ✗ {file_path} - tracking injection failed: {e}")
                    continue

            elif "single.html" in file_path or "article.html" in file_path:
                try:
                    patched = deployer._inject_internal_links_into_single(content)  # type: ignore
                    injection_note = "internal-links injected"
                except Exception as e:
                    print(f"  ✗ {file_path} - internal-links injection failed: {e}")
                    continue
            else:
                injection_note = "no injection"

            # Write patched content
            try:
                dest_file.write_text(patched)
                status = "✓" if not force else "✓ (overwritten)"
                print(f"  {status} {file_path} - {injection_note}")
            except Exception as e:
                print(f"  ✗ {file_path} - write error: {e}")
                continue
        else:
            # Just copy as-is
            try:
                shutil.copy2(source_file, dest_file)
                status = "✓" if not force else "✓ (overwritten)"
                print(f"  {status} {file_path}")
            except Exception as e:
                print(f"  ✗ {file_path} - copy error: {e}")
                continue


def main() -> None:
    """Extract Hugo theme overrides for all themes."""
    parser = argparse.ArgumentParser(
        description="Extract Hugo theme files to resources for override editing"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing override files",
    )
    parser.add_argument(
        "--inject",
        action="store_true",
        help="Apply tracking and internal-links injections (default: copy as-is)",
    )
    parser.add_argument(
        "--theme",
        type=str,
        help="Extract specific theme only (e.g., 'stack')",
    )
    args = parser.parse_args()

    # Paths
    project_root = Path(__file__).parent.parent
    storage_dir = project_root / "storage" / "hugo" / "themes"
    resources_dir = project_root / "resources" / "hugo" / "themes"

    # Validate storage directory
    if not storage_dir.exists():
        print(f"Error: Storage directory not found: {storage_dir}")
        print("Run scripts/download_hugo_themes.py first")
        sys.exit(1)

    # Create resources directory
    resources_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 80)
    print("EXTRACTING HUGO THEME OVERRIDES")
    print("=" * 80)
    print(f"\nStorage:   {storage_dir}")
    print(f"Resources: {resources_dir}")
    print(f"Mode:      {'inject' if args.inject else 'copy'}")
    print(f"Force:     {args.force}")

    # Determine which themes to process
    if args.theme:
        themes = [args.theme]
        if args.theme not in THEME_OVERRIDES:
            print(f"\nError: Unknown theme '{args.theme}'")
            print(f"Available: {', '.join(sorted(THEME_OVERRIDES.keys()))}")
            sys.exit(1)
    else:
        themes = sorted(THEME_OVERRIDES.keys())

    # Extract each theme
    for theme in themes:
        extract_theme_overrides(
            theme, storage_dir, resources_dir, args.force, args.inject
        )

    print("\n" + "=" * 80)
    print("EXTRACTION COMPLETE")
    print("=" * 80)
    print(f"\nOverrides saved to: {resources_dir}")


if __name__ == "__main__":
    start = time.perf_counter()
    main()
    end = time.perf_counter()
    elapsed = end - start
    print(f"Total time elapsed: {elapsed:.2f} seconds")
