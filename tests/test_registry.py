"""Unit tests for the Pet Package Registry."""

import json
import os
import pytest
from critter.core.registry import (
    DuplicatePackageError,
    ManifestValidationError,
    PetRegistry,
)


def test_registry_discover_valid_package():
    registry = PetRegistry(search_paths=["packages/pets"])
    packages = registry.discover()

    assert "dog" in packages
    dog = packages["dog"]
    assert dog.name == "Corgi"
    assert dog.species == "dog"
    assert dog.version == "1.0.0"
    assert dog.width == 160
    assert dog.height == 135
    assert "idle" in dog.animations
    assert len(dog.animations["idle"].frames) == 4


def test_registry_custom_search_path(tmp_path):
    # Create a custom pet package
    custom_dir = tmp_path / "custom_pet"
    custom_dir.mkdir()
    assets_dir = custom_dir / "assets"
    assets_dir.mkdir()

    # Create dummy frame
    from PIL import Image
    frame_path = assets_dir / "frame.png"
    img = Image.new("RGBA", (64, 64), (255, 0, 0, 255))
    img.save(frame_path)

    manifest_data = {
        "id": "fox",
        "name": "Kitsune",
        "species": "fox",
        "version": "0.1.0",
        "size": {"width": 64, "height": 64},
        "default_animation": "idle",
        "animations": {
            "idle": {
                "fps": 2,
                "loop": True,
                "frames": ["assets/frame.png"]
            }
        }
    }
    with open(custom_dir / "manifest.json", "w") as f:
        json.dump(manifest_data, f)

    registry = PetRegistry(search_paths=[str(tmp_path)])
    packages = registry.discover()
    assert "fox" in packages
    assert registry.get("fox").name == "Kitsune"


def test_registry_detects_duplicate_id(tmp_path):
    # Two packages with the same ID 'twin'
    for name in ["pet_a", "pet_b"]:
        pkg_dir = tmp_path / name
        pkg_dir.mkdir()
        (pkg_dir / "assets").mkdir()

        from PIL import Image
        img = Image.new("RGBA", (32, 32), (0, 255, 0, 255))
        img.save(pkg_dir / "assets" / "f.png")

        manifest = {
            "id": "twin",
            "name": f"Twin {name}",
            "species": "dog",
            "version": "1.0.0",
            "size": {"width": 32, "height": 32},
            "default_animation": "idle",
            "animations": {
                "idle": {"fps": 1, "frames": ["assets/f.png"]}
            }
        }
        with open(pkg_dir / "manifest.json", "w") as f:
            json.dump(manifest, f)

    registry = PetRegistry(search_paths=[str(tmp_path)])
    with pytest.raises(DuplicatePackageError, match="Duplicate pet package ID 'twin'"):
        registry.discover()


def test_registry_rejects_path_traversal(tmp_path):
    pkg_dir = tmp_path / "hacker_pet"
    pkg_dir.mkdir()

    manifest = {
        "id": "hacker",
        "name": "Hacker Pet",
        "species": "cat",
        "version": "1.0.0",
        "size": {"width": 32, "height": 32},
        "default_animation": "idle",
        "animations": {
            "idle": {"fps": 1, "frames": ["../../etc/passwd"]}
        }
    }
    with open(pkg_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    with pytest.raises(ManifestValidationError, match="Unsafe frame path"):
        PetRegistry.load_and_validate_package(str(pkg_dir))


def test_registry_rejects_missing_fields(tmp_path):
    pkg_dir = tmp_path / "broken_pet"
    pkg_dir.mkdir()

    manifest = {
        "id": "broken",
        # missing name, species, version, size
    }
    with open(pkg_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    with pytest.raises(ManifestValidationError, match="missing required field"):
        PetRegistry.load_and_validate_package(str(pkg_dir))


def test_registry_rejects_invalid_semver(tmp_path):
    pkg_dir = tmp_path / "bad_ver"
    pkg_dir.mkdir()

    manifest = {
        "id": "badver",
        "name": "Bad Ver",
        "species": "dog",
        "version": "v1-latest-beta",
        "size": {"width": 32, "height": 32},
        "default_animation": "idle",
        "animations": {}
    }
    with open(pkg_dir / "manifest.json", "w") as f:
        json.dump(manifest, f)

    with pytest.raises(ManifestValidationError, match="Invalid semantic version"):
        PetRegistry.load_and_validate_package(str(pkg_dir))

