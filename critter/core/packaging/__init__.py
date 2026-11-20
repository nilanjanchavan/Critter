"""Packaging, validation, export, and installation tools for Critter pet packages."""

from critter.core.packaging.validator import (
    PackageValidationError,
    PackageValidationResult,
    validate_package,
    validate_package_directory,
)
from critter.core.packaging.security import (
    ArchiveSecurityError,
    safe_extract_tar,
    safe_extract_zip,
    validate_tar_archive,
    validate_zip_archive,
)
from critter.core.packaging.exporter import (
    PackageExportError,
    compute_sha256,
    export_package,
)
from critter.core.packaging.installer import (
    BuiltinPackageCollisionError,
    PackageAlreadyInstalledError,
    PackageInstallError,
    install_package,
)

__all__ = [
    "ArchiveSecurityError",
    "BuiltinPackageCollisionError",
    "PackageAlreadyInstalledError",
    "PackageExportError",
    "PackageInstallError",
    "PackageValidationError",
    "PackageValidationResult",
    "compute_sha256",
    "export_package",
    "install_package",
    "safe_extract_tar",
    "safe_extract_zip",
    "validate_package",
    "validate_package_directory",
    "validate_tar_archive",
    "validate_zip_archive",
]

