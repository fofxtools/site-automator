"""Prepare WordOps server for site automation."""

from time import perf_counter

from site_automator.utils import configure_logging
from site_automator.wordops import WordOpsProvisioner


def main() -> None:
    configure_logging()

    wordops = WordOpsProvisioner.from_env()
    try:
        wordops.ensure_default_catchall()
        wordops.ensure_swap()
    finally:
        wordops.close()


if __name__ == "__main__":
    start_time = perf_counter()
    main()
    elapsed = perf_counter() - start_time
    print(f"Completed in {elapsed:.2f} seconds")
