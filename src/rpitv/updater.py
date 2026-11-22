import logging
import subprocess
import hmac
from pathlib import Path

logger = logging.getLogger(__name__)


def run_command(command, timeout, cwd):
    result = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout,
    )

    if result.returncode:
        logger.error(
            "Command '%s' failed with exit code %d; stderr:\n%s",
            " ".join(command),
            result.returncode,
            result.stderr.strip() or "(empty)",
        )
        raise subprocess.CalledProcessError(
            result.returncode,
            command,
            output=result.stdout,
            stderr=result.stderr,
        )
    return result


def get_remote_url(repository: Path):
    """ return remote url of git repository """
    result = run_command(
        ["git", "remote", "get-url", "origin"],
        timeout=15,
        cwd=repository,
    )
    return result.stdout.strip()

  

def get_branch(repository: Path):
    """ return branch of git repository """
    result = run_command(
        ["git", "branch", "--show-current"],
        timeout=15,
        cwd=repository,
    )
    return result.stdout.strip()


def get_local_changes(repository: Path):
    """ return git working tree of """
    result = run_command(
        ["git", "status", "--porcelain"],
        timeout=15,
        cwd=repository,
    )
    return result.stdout.strip()


def checkout_to_branch(repository: Path, branch:str):
    local_changes = get_local_changes(repository)
    if local_changes:
        raise RuntimeError("Unstaged changes. Stash them before checkout to master")
    result = run_command(
        ["git", "checkout", branch],
        timeout=15,
        cwd=repository,
    )
    return result.stdout.strip()


def stash_local_changes(repository: Path):
    """Stash local changes in the repository. And return stash hash to be able to pop it later. If no changes are detected, return None."""
    local_changes = get_local_changes(repository)

    if local_changes:
        run_command(
            ["git", "stash", "push", "--include-untracked", "-m", "rpitv automatic update backup"],
            timeout=30,
            cwd=repository,
        )
        stash_hash = run_command(
            ["git", "stash", "list", "-1", "--format=%H"],
            timeout=15,
            cwd=repository,
        ).stdout.strip()
        logger.warning(f"Local changes stashed >> {stash_hash}")

        return stash_hash
    else:
        return None

def restore_stashed_changes(repository: Path, stash_hash):
    """Restore stashed changes in the repository. If stash_hash is None, do nothing."""
    run_command(
        ["git", "stash", "apply", "--index", stash_hash],
        timeout=30,
        cwd=repository,
    )


def pull_and_update(repository: Path, branch:str):
    run_command(
        ["git", "pull", "--ff-only", "origin", branch],
        timeout=300,
        cwd=repository,
    )
    run_command(
        ["bash", "install-rpitv.sh", "--update-only"],
        timeout=300,
        cwd=repository,
    )