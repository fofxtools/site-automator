#!/usr/bin/env python3
"""Download Hugo themes from config/themes.toml to local storage directory."""

import subprocess
import sys
import tomllib
from pathlib import Path
import shutil


def main() -> None:
    """Download all themes from config to storage/hugo/themes."""
    # Load themes config
    config_file = Path(__file__).parent.parent / "config" / "themes.toml"
    
    if not config_file.exists():
        print(f"Error: {config_file} not found")
        sys.exit(1)
    
    with config_file.open("rb") as f:
        data = tomllib.load(f)
    
    themes = data.get("themes", {})
    if not themes:
        print("No themes found in config")
        sys.exit(1)
    
    # Create target directory
    target_dir = Path(__file__).parent.parent / "storage" / "hugo" / "themes"
    target_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Downloading {len(themes)} themes to {target_dir}")
    
    # Download each theme
    for theme_name, theme_data in themes.items():
        url = theme_data.get("url")
        commit = theme_data.get("commit")
        
        if not url or not commit:
            print(f"Skipping {theme_name}: missing url or commit")
            continue
        
        theme_path = target_dir / theme_name
        
        # Delete if already exists
        if theme_path.exists():
            print(f"Deleting existing {theme_name}...")
            shutil.rmtree(theme_path)
        
        print(f"Cloning {theme_name}...")
        try:
            subprocess.run(
                ["git", "clone", url, str(theme_path)],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "checkout", commit],
                cwd=theme_path,
                check=True,
                capture_output=True,
            )
            print(f"✓ {theme_name} @ {commit[:8]}")
        except subprocess.CalledProcessError as e:
            print(f"✗ {theme_name}: {e}")
    
    print("Done!")


if __name__ == "__main__":
    main()

