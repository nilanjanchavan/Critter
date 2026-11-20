"""Pet package validation engine.

Validates:
- Manifest JSON schema, semver, and required fields.
- Asset file references and path constraints.
- Image integrity, PNG format, exact width/height match.
- Genuine transparency (verifying presence of alpha < 255 pixels).
- Archive security (delegates to security.py).
"""

from dataclasses import dataclass, field
import json
import logging
import os
import re
import tempfile
from typing import Any, Dict, List, Optional, Set
from PIL import Image

from critter.core.packaging.security import (
    ArchiveSecurityError,
    safe_extract_tar,
    safe_extract_zip,
)

logger = logging.getLogger(__name__)

SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")
ID_REGEX = re.compile(r"^[a-zA-Z0-9_-]+$")


class PackageValidationError(Exception):
    """Raised when a package fails structural, manifest, or asset validation."""


@dataclass
class PackageValidationResult:
    """Summary result of a package validation check."""
    is_valid: bool
    package_id: str = ""
    name: str = ""
    version: str = ""
    species: str = ""
    width: int = 0
    height: int = 0
    animation_count: int = 0
    frame_count: int = 0
    file_count: int = 0
    total_size_bytes: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


def validate_png_transparency(img: Image.Image, allow_opaque: bool = False) -> bool:
    """Verify that an image contains actual transparent pixels (alpha < 255).

    Returns True if transparency is verified or allow_opaque is True.
    Raises PackageValidationError if image is 100% opaque without permission.
    """
    if allow_opaque:
        return True

    if img.mode not in ("RGBA", "LA", "PA") and "transparency" not in img.info:
        raise PackageValidationError(
            f"Image mode '{img.mode}' lacks an alpha channel. Pet artwork must be transparent PNG (mode RGBA) "
            "unless 'allow_opaque': true is explicitly configured in manifest.json."
        )

    # Convert to RGBA to inspect alpha channel reliably
    rgba_img = img.convert("RGBA")
    alpha_channel = rgba_img.getchannel("A")
    min_alpha, max_alpha = alpha_channel.getextrema()

    if min_alpha >= 255:
        raise PackageValidationError(
            "Image has an alpha channel but contains 0 transparent pixels (minimum alpha is 255). "
            "Desktop pet frames must have transparent background cutouts unless 'allow_opaque': true is declared in manifest."
        )

    return True


def validate_package_directory(package_dir: str) -> PackageValidationResult:
    """Validate an unpacked pet package directory in-place."""
    abs_dir = os.path.abspath(package_dir)
    if not os.path.isdir(abs_dir):
        raise PackageValidationError(f"Package directory does not exist: {package_dir}")

    manifest_path = os.path.join(abs_dir, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise PackageValidationError(f"Missing required 'manifest.json' at root of package directory: {package_dir}")

    try:
        with open(manifest_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        raise PackageValidationError(f"Invalid manifest.json: {exc}") from exc

    if not isinstance(data, dict):
        raise PackageValidationError("manifest.json must contain a root JSON object")

    # 1. Required manifest fields
    required = ["id", "name", "species", "version", "size", "default_animation", "animations"]
    for field_name in required:
        if field_name not in data or data[field_name] is None:
            raise PackageValidationError(f"manifest.json missing required field: '{field_name}'")

    pkg_id = str(data["id"]).strip()
    if not ID_REGEX.match(pkg_id):
        raise PackageValidationError(f"Invalid package ID '{pkg_id}'. Must be alphanumeric with '_' or '-'.")

    version = str(data["version"]).strip()
    if not SEMVER_REGEX.match(version):
        raise PackageValidationError(f"Invalid version '{version}'. Expected semantic versioning (e.g. 1.0.0).")

    # 2. Size validation
    size_spec = data["size"]
    if not isinstance(size_spec, dict) or "width" not in size_spec or "height" not in size_spec:
        raise PackageValidationError("Size must be an object with integer 'width' and 'height'")

    try:
        width = int(size_spec["width"])
        height = int(size_spec["height"])
        if width <= 0 or height <= 0:
            raise ValueError()
    except (ValueError, TypeError):
        raise PackageValidationError("Size 'width' and 'height' must be positive integers")

    # 3. Animations validation
    animations = data["animations"]
    if not isinstance(animations, dict) or not animations:
        raise PackageValidationError("manifest.json 'animations' must be a non-empty object")

    default_anim = str(data["default_animation"])
    if default_anim not in animations:
        raise PackageValidationError(f"default_animation '{default_anim}' is not defined in 'animations'")

    allow_opaque = bool(data.get("allow_opaque", False))

    total_frames = 0
    all_referenced_files: Set[str] = {manifest_path}

    for anim_name, anim_spec in animations.items():
        if not isinstance(anim_spec, dict):
            raise PackageValidationError(f"Animation '{anim_name}' must be an object")

        frames = anim_spec.get("frames", [])
        if not isinstance(frames, list) or not frames:
            raise PackageValidationError(f"Animation '{anim_name}' must contain a non-empty 'frames' list")

        fps = anim_spec.get("fps", 4)
        if not isinstance(fps, (int, float)) or fps <= 0:
            raise PackageValidationError(f"Animation '{anim_name}' fps must be a positive number")

        for frame_rel in frames:
            if not isinstance(frame_rel, str) or not frame_rel.strip():
                raise PackageValidationError(f"Empty or non-string frame path in animation '{anim_name}'")

            # Path traversal check
            norm_rel = os.path.normpath(frame_rel.replace("\\", "/"))
            if norm_rel.startswith("..") or os.path.isabs(norm_rel):
                raise PackageValidationError(f"Unsafe frame path '{frame_rel}' in animation '{anim_name}'")

            frame_abs = os.path.abspath(os.path.join(abs_dir, norm_rel))
            if os.path.commonpath([abs_dir, frame_abs]) != abs_dir:
                raise PackageValidationError(f"Frame path '{frame_rel}' escapes package directory")

            if not os.path.isfile(frame_abs):
                raise PackageValidationError(f"Frame file not found on disk: '{norm_rel}' (animation '{anim_name}')")

            # Image decoding and dimension verification
            try:
                with Image.open(frame_abs) as img:
                    img_w, img_h = img.size
                    if img_w != width or img_h != height:
                        raise PackageValidationError(
                            f"Dimension mismatch in '{norm_rel}': got {img_w}x{img_h}, manifest specifies {width}x{height}"
                        )
                    validate_png_transparency(img, allow_opaque=allow_opaque)
            except PackageValidationError:
                raise
            except Exception as exc:
                raise PackageValidationError(f"Corrupted or invalid image in '{norm_rel}': {exc}") from exc

            all_referenced_files.add(frame_abs)
            total_frames += 1

    # Calculate package stats
    file_count = 0
    total_size = 0
    for root, _, files in os.walk(abs_dir):
        for f in files:
            file_count += 1
            fpath = os.path.join(root, f)
            total_size += os.path.getsize(fpath)

    return PackageValidationResult(
        is_valid=True,
        package_id=pkg_id,
        name=str(data["name"]),
        version=version,
        species=str(data["species"]),
        width=width,
        height=height,
        animation_count=len(animations),
        frame_count=total_frames,
        file_count=file_count,
        total_size_bytes=total_size,
    )


def validate_package(path_or_archive: str) -> PackageValidationResult:
    """Validate a pet package from a directory or archive (.tar.gz, .tar.bz2, .tar.xz, .zip).

    Extracts archives into an isolated temporary staging directory for validation.
    """
    target = os.path.abspath(path_or_archive)
    if not os.path.exists(target):
        raise PackageValidationError(f"Package path does not exist: {path_or_archive}")

    if os.path.isdir(target):
        return validate_package_directory(target)

    # Archive validation
    lower_target = target.lower()
    is_tar = any(lower_target.endswith(ext) for ext in [".tar.gz", ".tgz", ".tar.bz2", ".tbz2", ".tar.xz", ".txz", ".tar"])
    is_zip = lower_target.endswith(".zip")

    if not (is_tar or is_zip):
        raise PackageValidationError(f"Unsupported package archive format. Expected .tar.gz or .zip: {path_or_archive}")

    with tempfile.TemporaryDirectory(prefix="critter_pkg_val_") as temp_dir:
        try:
            if is_tar:
                safe_extract_tar(target, temp_dir)
            else:
                safe_extract_zip(target, temp_dir)
        except ArchiveSecurityError as ase:
            raise PackageValidationError(f"Archive security violation: {ase}") from ase
        except Exception as exc:
            raise PackageValidationError(f"Failed extracting archive: {exc}") from exc

        # If archive extracted into a single top-level directory (e.g. package_name/manifest.json)
        entries = os.listdir(temp_dir)
        if len(entries) == 1 and os.path.isdir(os.path.join(temp_dir, entries[0])) and not os.path.isfile(os.path.join(temp_dir, "manifest.json")):
            effective_dir = os.path.join(temp_dir, entries[0])
        else:
            effective_dir = temp_dir

        return validate_package_directory(effective_dir)

