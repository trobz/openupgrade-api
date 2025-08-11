import argparse
from pathlib import Path

from upgrade_analysis_parser.processing.sync import clone_or_pull_repo, extract_data_for_version
from upgrade_analysis_parser.processing.parser import run_parse_for_version

REPO_URL = "https://github.com/OCA/OpenUpgrade.git"
LOCAL_REPO_PATH = Path("./OpenUpgrade_Repo")
DATA_SOURCES_PATH = Path("./data_sources")
DB_DIR = Path("./databases")

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for command-line tasks (sync, parse)."""
    DATA_SOURCES_PATH.mkdir(exist_ok=True)
    DB_DIR.mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="OpenUpgrade Analyzer - Data Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Sync and extract data from OpenUpgrade versions.")
    sync_parser.add_argument(
        "--versions",
        nargs="+",
        type=int,
        default=[16, 17, 18],
        help="A list of major versions to sync (e.g., 18 17).",
    )

    parse_parser = subparsers.add_parser("parse", help="Parse a specific major version.")
    parse_parser.add_argument(
        "--versions",
        nargs="+",
        type=int,
        default=[16, 17, 18],
        help="Major version to parse (e.g., 18).",
    )

    args = parser.parse_args()

    if args.command == "sync":
        repo = clone_or_pull_repo(REPO_URL, LOCAL_REPO_PATH)
        for version in args.versions:
            extract_data_for_version(repo, version, DATA_SOURCES_PATH)

    elif args.command == "parse":
        for version in args.versions:
            version_scripts_path = DATA_SOURCES_PATH / str(version)
            if not version_scripts_path.exists():
                logger.error(
                    f"Source directory not found for version {version}."
                )
                logger.error(
                    f"Please run 'python manage.py sync --versions {version}' first."
                )
                return
            run_parse_for_version(version, version_scripts_path, DB_DIR)


if __name__ == "__main__":
    main()