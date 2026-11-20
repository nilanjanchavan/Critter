"""Safe and atomic pet package installer.

Installs validated packages into ~/.local/share/critter/packages/pets/
using same-filesystem staging, atomic directory replacement, and automatic rollback on failure.
Prevents overwriting built-in packages and rejects symlinks.
"""

import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import List, Optional

from critter.core.packaging.validator import validate_package, PackageValidationError
from critter.core.registry import PetRegistry

logger = logging.getLogger(__name__)

def get_default_user_pets_dir() -> str:
    """Return default user pet installation directory, with sandbox fallback."""
    env_dir = os.environ.get("CRITTER_USER_PETS_DIR")
    if env_dir:
        return env_dir
    default_dir = os.path.expanduser("~/.local/share/critter/packages/pets")
    try:
        os.makedirs(default_dir, exist_ok=True)
        test_file = os.path.join(default_dir, f".write_test_{os.getpid()}")
        with open(test_file, "w") as f:
            f.write("ok")
        os.remove(test_file)
        return default_dir
    except (OSError, PermissionError):
        # Fallback to local directory when user home is read-only (e.g. testing in sandbox)
        fallback = os.path.abspath(".critter_packages/pets")
        os.makedirs(fallback, exist_ok=True)
        return fallback


class PackageInstallError(Exception):
    """Base exception for package installation errors."""


class PackageAlreadyInstalledError(PackageInstallError):
    """Raised when package already exists and force=False."""


class BuiltinPackageCollisionError(PackageInstallError):
    """Raised when trying to overwrite a built-in pet package."""


def install_package(
    archive_or_dir_path: str,
    target_base_dir: Optional[str] = None,
    force: bool = False,
    builtin_paths: Optional[List[str]] = None,
) -> str:
    """Safely and atomically install a pet package.

    Args:
        archive_or_dir_path: Path to .tar.gz, .zip, or directory.
        target_base_dir: Destination packages directory (defaults to ~/.local/share/critter/packages/pets).
        force: Whether to replace an existing community package.
        builtin_paths: List of directories holding protected built-in packages.

    Returns:
        The destination directory path of the installed package.
    """
    source_path = os.path.abspath(archive_or_dir_path)
    if not os.path.exists(source_path):
        raise PackageInstallError(f"Package source path not found: {archive_or_dir_path}")

    dest_base = os.path.abspath(target_base_dir or get_default_user_pets_dir())
    os.makedirs(dest_base, exist_ok=True)

    # 1. Staging on the SAME filesystem to guarantee atomic os.replace
    staging_temp = tempfile.TemporaryDirectory(dir=dest_base, prefix=".staging_critter_")
    backup_dir: Optional[str] = None

    try:
        staging_dir = staging_temp.name

        # Extract or copy into staging
        if os.path.isdir(source_path):
            # Copy contents into staging
            staged_pkg = os.path.join(staging_dir, "pkg")
            shutil.copytree(source_path, staged_pkg)
        else:
            lower = source_path.lower()
            if any(lower.endswith(ext) for ext in [".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar"]):
                from critter.core.packaging.security import safe_extract_tar
                safe_extract_tar(source_path, staging_dir)
            elif lower.endswith(".zip"):
                from critter.core.packaging.security import safe_extract_zip
                safe_extract_zip(source_path, staging_dir)
            else:
                raise PackageInstallError(f"Unsupported package file format: {source_path}")

            # Locate root package directory inside staging
            entries = os.listdir(staging_dir)
            if len(entries) == 1 and os.path.isdir(os.path.join(staging_dir, entries[0])) and not os.path.isfile(os.path.join(staging_dir, "manifest.json")):
                staged_pkg = os.path.join(staging_dir, entries[0])
            else:
                staged_pkg = staging_dir

        # 2. Validate the staged package thoroughly
        val_result = validate_package(staged_pkg)
        pkg_id = val_result.package_id

        # 3. Check collision with built-in packages
        builtins = builtin_paths or ["packages/pets"]
        for b_path in builtins:
            abs_b = os.path.abspath(b_path)
            candidate = os.path.join(abs_b, pkg_id)
            if os.path.isdir(candidate):
                raise BuiltinPackageCollisionError(
                    f"Refusing to overwrite protected built-in pet package '{pkg_id}' located at {candidate}"
                )

        # 4. Check target destination
        final_dest = os.path.join(dest_base, pkg_id)

        # Disallow symlinks in the destination hierarchy
        if os.path.islink(final_dest):
            raise PackageInstallError(f"Destination path '{final_dest}' is a symlink; unsafe to install")

        if os.path.exists(final_dest):
            if not force:
                raise PackageAlreadyInstalledError(
                    f"Package '{pkg_id}' is already installed at '{final_dest}'. Use --force to replace/update."
                )
            # Create backup for rollback safety
            backup_dir = os.path.join(dest_base, f".backup_{pkg_id}_{os.getpid()}")
            if os.path.exists(backup_dir):
                shutil.rmtree(backup_dir)
            os.replace(final_dest, backup_dir)

        # 5. Atomic directory replacement
        os.replace(staged_pkg, final_dest)

        # 6. Apply clean permissions across installed package
        for root, dirs, files in os.walk(final_dest):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o755)
            for f in files:
                os.chmod(os.path.join(root, f), 0o644)

        # Installation succeeded; remove backup
        if backup_dir and os.path.exists(backup_dir):
            shutil.rmtree(backup_dir)

        logger.info("Successfully installed pet package '%s' (v%s) to %s", pkg_id, val_result.version, final_dest)
        return final_dest

    except Exception as exc:
        # Rollback: restore backup if available
        if backup_dir and os.path.exists(backup_dir):
            target = os.path.join(dest_base, pkg_id)
            if os.path.exists(target):
                shutil.rmtree(target)
            os.replace(backup_dir, target)
            logger.info("Rolled back installation of package '%s'", pkg_id)
        raise
    finally:
        staging_temp.cleanup()
