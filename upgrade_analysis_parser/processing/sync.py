import sys
import subprocess
from pathlib import Path
import shutil
import git
from tqdm import tqdm

import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CloneProgress(git.remote.RemoteProgress):
    def __init__(self):
        super().__init__()
        self.pbar = tqdm(leave=False)

    def update(self, op_code, cur_count, max_count=None, message=''):
        self.pbar.total = max_count
        self.pbar.n = cur_count
        self.pbar.refresh()
        if cur_count == max_count:
            self.pbar.close()


def clone_or_pull_repo(repo_url: str, local_path: Path):
    logger.info("--- Step 1: Ensuring local repository exists ---")
    if local_path.is_dir():
        logger.info(f"Repository already exists at {local_path}.")
        return git.Repo(local_path)
    else:
        logger.info(f"Cloning repository from {repo_url} into {local_path}...")
        try:
            repo = git.Repo.clone_from(
                repo_url, local_path, progress=CloneProgress()
            )
            logger.info("Clone complete.")
            return repo
        except git.exc.GitCommandError as e:
            logger.error(
                f"An error occurred during git clone: {e}", file=sys.stderr
            )
            sys.exit(1)


def extract_data_for_version(repo: git.Repo, major_version: int, base_dest_path: Path):
    branch = f"{major_version}.0"
    version_dest_path = base_dest_path / str(major_version)

    logger.info(
        f"\n--- Step 2: Processing data for branch '{branch}' ---"
    )

    try:
        logger.info(f"Fetching latest data for branch '{branch}'...")
        repo.remotes.origin.fetch(branch, prune=True)
    except git.exc.GitCommandError as e:
        logger.warning(
            f"WARNING: Could not fetch branch '{branch}'. It might not exist on the remote. Error: {e}",
            file=sys.stderr,
        )
        return

    if f"origin/{branch}" not in [str(r) for r in repo.remotes.origin.refs]:
        logger.warning(
            f"WARNING: Branch '{branch}' not found in remote repository after fetch. Skipping.",
            file=sys.stderr,
        )
        return

    if version_dest_path.exists():
        shutil.rmtree(version_dest_path)
    version_dest_path.mkdir(parents=True)

    source_path_in_repo = "openupgrade_scripts/scripts"

    command = f"""
        git -C "{repo.working_dir}" archive origin/{branch} {source_path_in_repo} | \
        tar -x --strip-components=2 -C "{version_dest_path}"
    """

    logger.info(
        f"Extracting '{source_path_in_repo}' from local branch '{branch}'..."
    )
    try:
        subprocess.run(
            command, shell=True, check=True, capture_output=True, text=True
        )
        logger.info(f"Successfully extracted data to {version_dest_path}")
    except subprocess.CalledProcessError as e:
        logger.error(
            f"ERROR: Failed to extract data for branch '{branch}'.",
            file=sys.stderr,
        )
        logger.error(f"Command Error: {e.stderr}", file=sys.stderr)
        if version_dest_path.exists():
            shutil.rmtree(version_dest_path)
