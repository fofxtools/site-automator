"""Prepare WordOps server for site automation.

Usage:
    python examples/prepare_wordops_server.py --server <server>
"""

import argparse
from time import perf_counter

from site_automator.utils import configure_logging
from site_automator.wordops import WordOpsProvisioner


def main() -> None:
    configure_logging()

    parser = argparse.ArgumentParser(description="Prepare WordOps server")
    parser.add_argument(
        "--server",
        required=True,
        help="SSH host alias from ~/.ssh/config (e.g., your-server-alias)",
    )
    args = parser.parse_args()

    wordops = WordOpsProvisioner(host=args.server)
    try:
        wordops.ensure_default_catchall()
        wordops.ensure_swap()
        wordops.ensure_git_safe_directory()
    finally:
        wordops.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    elapsed = perf_counter() - start_time
    print(f"Completed in {elapsed:.2f} seconds")
