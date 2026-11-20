"""Pet package export engine.

Bundles a validated pet package into a clean, distributable .tar.gz or .zip archive
with companion SHA-256 checksum, excluding development files, Python scripts, and caches.
"""

import hashlib
import json
import logging
import os
import posixpath
import tarfile
from typing import List, Optional, Set, Tuple
import zipfile

from critter.core.packaging.validator import validate_package
from critter.core.registry import PetRegistry

logger = logging.getLogger(__name__)

# Permitted metadata files to include if present in package root
OPTIONAL_METADATA_FILES = {"readme.md", "license", "license.txt", "license.md", "icon.png", "preview.png"}


class PackageExportError(Exception):
    """Raised when package export fails."""


def compute_sha256(file_path: str) -> str:
    """Compute SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def export_package(
    package_id_or_path: str,
    output_path: Optional[str] = None,
    archive_format: str = "tar.gz",
    registry: Optional[PetRegistry] = None,
) -> Tuple[str, str]:
    """Export a pet package to a clean, distributable archive with SHA-256 checksum.

    Returns:
        (archive_file_path, sha256_checksum)
    """
    pkg_dir: str = ""

    # Check if direct directory was provided
    if os.path.isdir(package_id_or_path):
        pkg_dir = os.path.abspath(package_id_or_path)
    else:
        # Search via registry
        reg = registry or PetRegistry()
        reg.discover()
        manifest = reg.get(package_id_or_path)
        if not manifest:
            raise PackageExportError(f"Package ID '{package_id_or_path}' not found in registry search paths")
        pkg_dir = manifest.package_dir

    # 1. Validate package before export
    val_result = validate_package(pkg_dir)
    pkg_id = val_result.package_id
    version = val_result.version

    # Read manifest to extract exact referenced files
    manifest_path = os.path.join(pkg_dir, "manifest.json")
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest_data = json.load(f)

    # 2. Collect only explicit, verified files to include
    seen_arc_paths: Set[str] = set()
    files_to_bundle: List[Tuple[str, str]] = []  # (abs_path, arc_rel_path)

    manifest_arc = posixpath.join(pkg_id, "manifest.json")
    files_to_bundle.append((manifest_path, manifest_arc))
    seen_arc_paths.add(manifest_arc)

    for anim_name, anim_spec in manifest_data.get("animations", {}).items():
        for frame_rel in anim_spec.get("frames", []):
            norm_rel = os.path.normpath(frame_rel.replace("\\", "/"))
            frame_abs = os.path.abspath(os.path.join(pkg_dir, norm_rel))
            arc_rel = posixpath.join(pkg_id, norm_rel.replace(os.sep, "/"))
            if arc_rel not in seen_arc_paths:
                files_to_bundle.append((frame_abs, arc_rel))
                seen_arc_paths.add(arc_rel)

    # Add optional documentation if present
    for fname in os.listdir(pkg_dir):
        if fname.lower() in OPTIONAL_METADATA_FILES:
            fpath = os.path.join(pkg_dir, fname)
            if os.path.isfile(fpath):
                arc_rel = posixpath.join(pkg_id, fname)
                if arc_rel not in seen_arc_paths:
                    files_to_bundle.append((fpath, arc_rel))
                    seen_arc_paths.add(arc_rel)

    # Determine output path
    clean_fmt = archive_format.lower().lstrip(".")
    if clean_fmt in ("tar.gz", "tgz", "gz"):
        ext = "tar.gz"
    elif clean_fmt == "zip":
        ext = "zip"
    else:
        raise PackageExportError(f"Unsupported archive format '{archive_format}'. Expected 'tar.gz' or 'zip'.")

    if output_path:
        final_archive_path = os.path.abspath(output_path)
    else:
        final_archive_path = os.path.abspath(f"{pkg_id}-v{version}.{ext}")

    os.makedirs(os.path.dirname(final_archive_path), exist_ok=True)

    # 3. Create archive
    if ext == "tar.gz":
        with tarfile.open(final_archive_path, "w:gz") as tar:
            for abs_path, arc_path in files_to_bundle:
                ti = tar.gettarinfo(abs_path, arcname=arc_path)
                # Normalize ownership and permissions
                ti.uid = 1000
                ti.gid = 1000
                ti.uname = "critter"
                ti.gname = "critter"
                ti.mode = 0o644
                with open(abs_path, "rb") as f:
                    tar.addfile(ti, f)
    else:
        with zipfile.ZipFile(final_archive_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for abs_path, arc_path in files_to_bundle:
                zf.write(abs_path, arcname=arc_path)

    # 4. Generate SHA-256 checksum
    sha256_hash = compute_sha256(final_archive_path)
    checksum_file = f"{final_archive_path}.sha256"
    with open(checksum_file, "w", encoding="utf-8") as f:
        f.write(f"{sha256_hash}  {os.path.basename(final_archive_path)}\n")

    logger.info("Exported package '%s' (v%s) to %s (SHA-256: %s)", pkg_id, version, final_archive_path, sha256_hash)
    return final_archive_path, sha256_hash

