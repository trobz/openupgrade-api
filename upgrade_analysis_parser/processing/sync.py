# Copyright 2025 Trobz
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

import sys
import subprocess
from pathlib import Path
import shutil
import git
from tqdm import tqdm
import re

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
                repo_url, local_path, depth=1, progress=CloneProgress()
            )
            logger.info("Clone complete.")
            return repo
        except git.exc.GitCommandError as e:
            logger.error(
                f"An error occurred during git clone: {e}"
            )
            sys.exit(1)


def extract_data_for_version(repo: git.Repo, major_version: float, base_dest_path: Path):
    branch_ref = f"origin/{major_version}"

    logger.info(f"\n--- Step 2: Processing data for branch '{major_version}' ---")

    if branch_ref not in {str(r) for r in repo.remotes.origin.refs}:
        try:
            logger.info(f"Shallow fetching '{branch_ref}'...")
            repo.git.fetch("--depth=1", "origin", f"refs/heads/{str(major_version)}:refs/remotes/origin/{str(major_version)}")
        except git.exc.GitCommandError as e:
            logger.warning(f"Could not fetch branch '{major_version}'. Error: {e}")
            return

    repo.git.checkout(branch_ref)

    if major_version >= 14.0:
        version_dest_path = base_dest_path / str(major_version)
        if version_dest_path.exists():
            shutil.rmtree(version_dest_path)
        version_dest_path.mkdir(parents=True)

        extracted_scripts = False

        # Check openupgrade_scripts/scripts
        chk_scripts = subprocess.run(
            ["git", "-C", repo.working_dir, "ls-tree", "-d", "--name-only", branch_ref, "openupgrade_scripts/scripts"],
            capture_output=True, text=True
        )
        if chk_scripts.returncode == 0 and chk_scripts.stdout.strip():
            source_path_in_repo = "openupgrade_scripts/scripts"
            command = f"""
                git -C "{repo.working_dir}" archive {branch_ref} {source_path_in_repo} | \
                tar -x --strip-components=2 -C "{version_dest_path}"
            """
            logger.info(f"Extracting '{source_path_in_repo}' from '{branch_ref}' (strip-components=2)...")
            try:
                subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
                logger.info(f"Successfully extracted data to {version_dest_path}")
                extracted_scripts = True
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to extract '{source_path_in_repo}' for '{major_version}'. stderr:\n{e.stderr}")

        if not extracted_scripts:
            logger.warning("No migration scripts found in openupgrade_scripts/ for this branch.")

    else:
        logger.info("Extracting v13-style migration folders from addons/...")

        try:
            ls = subprocess.run(
                ["git", "-C", repo.working_dir, "ls-tree", "-d", "-r", branch_ref, "--name-only"],
                capture_output=True, text=True, check=True
            )
        except subprocess.CalledProcessError as e:
            logger.error(f"Cannot list directories for '{major_version}'. {e}")
            return

        dirs = ls.stdout.splitlines()
        pat = re.compile(r"^addons/([^/]+)/migrations/([^/]+)$")
        migration_dirs = [d for d in dirs if pat.match(d)]

        if not migration_dirs:
            logger.warning("No migration directories found for v13 or below.")
            return

        for mig_dir in migration_dirs:
            m = pat.match(mig_dir)
            module, migration_ver = m.group(1), m.group(2)
            dest_dir = base_dest_path / str(major_version) / module
            dest_dir.mkdir(parents=True, exist_ok=True)

            logger.info(f"Extracting '{mig_dir}' to '{dest_dir}' ...")
            try:
                subprocess.run(
                    f"git -C '{repo.working_dir}' archive {branch_ref} {mig_dir} | tar -x --strip-components=3 -C '{dest_dir}'",
                    shell=True, check=True
                )
                logger.info(f"Extracted migration for {module} {migration_ver}")
            except subprocess.CalledProcessError as e:
                logger.warning(f"Failed to extract '{mig_dir}'. stderr:\n{e.stderr}")

    logger.info(f"Done processing '{major_version}'.")
