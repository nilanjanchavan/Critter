"""Declarative Pet Package Registry.

Discovers, validates, and registers pet packages from local and user directories.
Completely independent of GTK and Wayland.
"""

from dataclasses import dataclass
import json
import logging
import os
import re
from typing import Dict, List, Optional
from PIL import Image
from critter.core.pet import AnimationDef, MovementConfig, PetManifest

logger = logging.getLogger(__name__)

# Semantic version pattern: MAJOR.MINOR.PATCH (e.g., 1.0.0, 0.2.1)
SEMVER_REGEX = re.compile(r"^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$")


class RegistryError(Exception):
    """Base exception for pet package registry errors."""


class ManifestValidationError(RegistryError):
    """Raised when a pet manifest fails validation."""


class DuplicatePackageError(RegistryError):
    """Raised when two pet packages share the same package ID."""


class PetRegistry:
    """Discovers and validates pet packages."""

    def __init__(self, search_paths: Optional[List[str]] = None) -> None:
        self.search_paths: List[str] = search_paths or ["packages/pets"]
        self._packages: Dict[str, PetManifest] = {}

    def register_search_path(self, path: str) -> None:
        """Add a custom search path to the registry."""
        resolved = os.path.abspath(path)
        if resolved not in self.search_paths:
            self.search_paths.append(resolved)

    def discover(self) -> Dict[str, PetManifest]:
        """Scan all search paths and load valid pet packages."""
        self._packages.clear()

        for base_path in self.search_paths:
            resolved_base = os.path.abspath(base_path)
            if not os.path.isdir(resolved_base):
                logger.debug("Search path does not exist, skipping: %s", resolved_base)
                continue

            for entry in sorted(os.listdir(resolved_base)):
                package_dir = os.path.join(resolved_base, entry)
                if not os.path.isdir(package_dir):
                    continue

                manifest_file = os.path.join(package_dir, "manifest.json")
                if os.path.isfile(manifest_file):
                    try:
                        manifest = self.load_and_validate_package(package_dir)
                        if manifest.id in self._packages:
                            existing_dir = self._packages[manifest.id].package_dir
                            raise DuplicatePackageError(
                                f"Duplicate pet package ID '{manifest.id}' found in '{package_dir}'. "
                                f"Already loaded from '{existing_dir}'."
                            )
                        self._packages[manifest.id] = manifest
                        logger.info("Registered pet package '%s' (v%s) from %s",
                                    manifest.id, manifest.version, package_dir)
                    except RegistryError as exc:
                        logger.warning("Failed to load pet package from %s: %s", package_dir, exc)
                        raise

        return self._packages

    def get(self, pet_id: str) -> Optional[PetManifest]:
        return self._packages.get(pet_id)

    def list_all(self) -> List[PetManifest]:
        return list(self._packages.values())

    @staticmethod
    def load_and_validate_package(package_dir: str) -> PetManifest:
        """Load and thoroughly validate a pet package manifest and its assets."""
        resolved_pkg_dir = os.path.abspath(package_dir)
        manifest_path = os.path.join(resolved_pkg_dir, "manifest.json")

        if not os.path.isfile(manifest_path):
            raise ManifestValidationError(f"Missing manifest.json in {package_dir}")

        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError as exc:
            raise ManifestValidationError(f"Invalid JSON in {manifest_path}: {exc}") from exc

        # 1. Required Fields Validation
        required_fields = ["id", "name", "species", "version", "size", "default_animation", "animations"]
        for field_name in required_fields:
            if field_name not in data or data[field_name] is None:
                raise ManifestValidationError(f"Manifest missing required field '{field_name}' in {manifest_path}")

        pet_id = str(data["id"]).strip()
        if not pet_id or not re.match(r"^[a-zA-Z0-9_-]+$", pet_id):
            raise ManifestValidationError(f"Invalid pet package ID '{pet_id}'. Must be alphanumeric.")

        # 2. Version validation
        version = str(data["version"]).strip()
        if not SEMVER_REGEX.match(version):
            raise ManifestValidationError(f"Invalid semantic version '{version}'. Expected format 'X.Y.Z'.")

        # 3. Size validation
        size_data = data["size"]
        if not isinstance(size_data, dict) or "width" not in size_data or "height" not in size_data:
            raise ManifestValidationError("Size must be an object with 'width' and 'height'.")

        try:
            width = int(size_data["width"])
            height = int(size_data["height"])
            if width <= 0 or height <= 0:
                raise ValueError()
        except (ValueError, TypeError):
            raise ManifestValidationError("Size 'width' and 'height' must be positive integers.")

        # 4. Animations validation
        anim_dict = data["animations"]
        if not isinstance(anim_dict, dict) or not anim_dict:
            raise ManifestValidationError("Package must define at least one animation in 'animations'.")

        default_anim = str(data["default_animation"])
        if default_anim not in anim_dict:
            raise ManifestValidationError(
                f"Default animation '{default_anim}' is not defined in 'animations'."
            )

        validated_animations: Dict[str, AnimationDef] = {}
        for anim_name, anim_spec in anim_dict.items():
            if not isinstance(anim_spec, dict):
                raise ManifestValidationError(f"Animation '{anim_name}' must be an object.")

            fps = int(anim_spec.get("fps", 4))
            loop = bool(anim_spec.get("loop", True))
            raw_frames = anim_spec.get("frames", [])

            if not isinstance(raw_frames, list) or not raw_frames:
                raise ManifestValidationError(f"Animation '{anim_name}' must have a non-empty 'frames' list.")

            resolved_frames: List[str] = []
            for frame_rel in raw_frames:
                # Security: prevent path traversal attacks (e.g. ../../etc/passwd)
                normalized_rel = os.path.normpath(frame_rel)
                if normalized_rel.startswith("..") or os.path.isabs(normalized_rel):
                    raise ManifestValidationError(
                        f"Unsafe frame path '{frame_rel}' in animation '{anim_name}'. Paths must be relative to package."
                    )

                abs_frame_path = os.path.abspath(os.path.join(resolved_pkg_dir, normalized_rel))

                # Verify the file is strictly contained within the package directory
                common = os.path.commonpath([resolved_pkg_dir, abs_frame_path])
                if common != resolved_pkg_dir:
                    raise ManifestValidationError(f"Asset path '{frame_rel}' escapes package directory.")

                if not os.path.isfile(abs_frame_path):
                    raise ManifestValidationError(
                        f"Asset frame missing on disk: '{abs_frame_path}' in animation '{anim_name}'"
                    )

                # Validate image header/integrity using PIL
                try:
                    with Image.open(abs_frame_path) as img:
                        img.verify()
                except Exception as exc:
                    raise ManifestValidationError(
                        f"Corrupted or invalid image file '{abs_frame_path}': {exc}"
                    ) from exc

                resolved_frames.append(abs_frame_path)

            validated_animations[anim_name] = AnimationDef(
                fps=fps,
                loop=loop,
                frames=resolved_frames,
            )

        # 5. Movement config
        mv_data = data.get("movement", {})
        movement = MovementConfig(
            speed=float(mv_data.get("speed", 75.0)),
            idle_min_seconds=float(mv_data.get("idle_min_seconds", 2.0)),
            idle_max_seconds=float(mv_data.get("idle_max_seconds", 6.0)),
            walk_min_seconds=float(mv_data.get("walk_min_seconds", 2.0)),
            walk_max_seconds=float(mv_data.get("walk_max_seconds", 5.0)),
        )

        return PetManifest(
            id=pet_id,
            name=str(data["name"]),
            species=str(data["species"]),
            version=version,
            author=str(data.get("author", "Unknown")),
            description=str(data.get("description", "")),
            width=width,
            height=height,
            default_animation=default_anim,
            animations=validated_animations,
            movement=movement,
            package_dir=resolved_pkg_dir,
        )

