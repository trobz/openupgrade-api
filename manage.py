import argparse
from pathlib import Path

from upgrade_analysis_parser.processing.sync import clone_or_pull_repo, extract_data_for_version
from upgrade_analysis_parser.processing.parser import run_parse_for_version
from upgrade_analysis_parser.processing.apriori import parse_apriori
from upgrade_analysis_parser.processing.get import (
    generate_removed_models,
    generate_removed_fields,
    generate_renamed_models,
    generate_renamed_fields,
)

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
    subparsers.add_parser("apriori", help="Parse apriori data")

    get_parser = subparsers.add_parser("get", help="Get data for odoo-module-migrator")
    get_parser.add_argument("--object-type", choices=["removed", "renamed"], required=True, help="Type of objects to get")
    get_parser.add_argument("--object", choices=["models", "fields"], required=True, help="Object to get data")
    get_parser.add_argument(
        "--versions",
        nargs="+",
        type=float,
        default=[16.0, 17.0, 18.0],
        help="Major versions to include (e.g., 18.0 17.0).",
    )
    get_parser.add_argument("--output-directory", type=str, default=".", help="Output directory")

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
            run_parse_for_version(version, version_scripts_path)
    elif args.command == "apriori":
        parse_apriori()

    elif args.command == "get":
        for version in args.versions:
            version_dir = Path(args.output_directory) / f"{args.object_type}_{args.object}" / f"migrate_{str(version - 1).replace('.', '')}_{str(version).replace('.', '')}"
            version_dir.mkdir(parents=True, exist_ok=True)
            if args.object_type == "removed":
                if args.object == "models":
                    generate_removed_models(version, version_dir)
                elif args.object == "fields":
                    generate_removed_fields(version, version_dir)
                else:
                    logger.error(f"Unsupported object: {args.object}")
            elif args.object_type == "renamed":
                if args.object == "models":
                    generate_renamed_models(version, version_dir)
                elif args.object == "fields":
                    generate_renamed_fields(version, version_dir)
                else:
                    logger.error(f"Unsupported object: {args.object}")
            else:
                logger.error(f"Unsupported object-type: {args.object_type}.")

if __name__ == "__main__":
    main()