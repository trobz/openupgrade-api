import argparse
from pathlib import Path

from upgrade_analysis_parser.processing.sync import clone_or_pull_repo, extract_data_for_version
from upgrade_analysis_parser.processing.parser import run_parse_for_version

from config import (
    OPENUPGRADE_REPO_URL,
    OPENUPGRADE_REPO_PATH,
    OPENUPGRADE_SCRIPTS_SOURCES_PATH,
    DB_PATH
)

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """Entry point for command-line tasks (sync, parse)."""
    Path(OPENUPGRADE_SCRIPTS_SOURCES_PATH).mkdir(exist_ok=True)
    Path(DB_PATH).mkdir(exist_ok=True)

    parser = argparse.ArgumentParser(description="OpenUpgrade Analyzer - Data Manager")
    subparsers = parser.add_subparsers(dest="command", required=True)

    sync_parser = subparsers.add_parser("sync", help="Sync and extract data from OpenUpgrade versions.")
    sync_parser.add_argument(
        "--versions",
        nargs="+",
        type=float,
        default=[16.0, 17.0, 18.0],
        help="A list of major versions to sync (e.g., 18.0 17.0).",
    )

    parse_parser = subparsers.add_parser("parse", help="Parse a specific major version.")
    parse_parser.add_argument(
        "--versions",
        nargs="+",
        type=float,
        default=[16.0, 17.0, 18.0],
        help="Major version to parse (e.g., 18.0).",
    )

    args = parser.parse_args()

    if args.command == "sync":
        repo = clone_or_pull_repo(OPENUPGRADE_REPO_URL, Path(OPENUPGRADE_REPO_PATH))
        for version in args.versions:
            extract_data_for_version(repo, version, Path(OPENUPGRADE_SCRIPTS_SOURCES_PATH))

    elif args.command == "parse":
        for version in args.versions:
            version_scripts_path = Path(OPENUPGRADE_SCRIPTS_SOURCES_PATH) / str(version)
            if not version_scripts_path.exists():
                logger.error(
                    f"Source directory not found for version {version}."
                )
                logger.error(
                    f"Please run 'python manage.py sync --versions {version}' first."
                )
                return
            run_parse_for_version(version, version_scripts_path, Path(DB_PATH))


if __name__ == "__main__":
    main()