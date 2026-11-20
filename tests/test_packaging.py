"""Comprehensive test suite for Critter pet package validation, export, installation, and security."""

import io
import json
import os
import shutil
import tarfile
import tempfile
import zipfile
import pytest
from PIL import Image

from critter.core.packaging.security import (
    ArchiveSecurityError,
    sanitize_and_validate_member_path,
    validate_tar_archive,
    validate_zip_archive,
    safe_extract_tar,
    safe_extract_zip,
)
from critter.core.packaging.validator import (
    PackageValidationError,
    validate_png_transparency,
    validate_package_directory,
    validate_package,
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
from critter.core.registry import PetRegistry
from critter.apps.desktop.main import handle_package_cli


def create_transparent_png(width: int = 64, height: int = 64) -> bytes:
    """Create a minimal PNG with both transparent and non-transparent pixels."""
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    # Fill middle pixels with opaque color
    for x in range(width // 4, 3 * width // 4):
        for y in range(height // 4, 3 * height // 4):
            img.putpixel((x, y), (255, 100, 50, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_opaque_png(width: int = 64, height: int = 64) -> bytes:
    """Create a 100% opaque PNG (all alpha == 255)."""
    img = Image.new("RGBA", (width, height), (255, 0, 0, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def create_mock_package_dir(
    dest_dir: str,
    pkg_id: str = "test_pet",
    version: str = "1.0.0",
    width: int = 64,
    height: int = 64,
    allow_opaque: bool = False,
    opaque_artwork: bool = False,
) -> str:
    """Create a valid mock pet package structure in dest_dir."""
    pkg_root = os.path.join(dest_dir, pkg_id)
    assets_dir = os.path.join(pkg_root, "assets")
    os.makedirs(assets_dir, exist_ok=True)

    png_bytes = create_opaque_png(width, height) if opaque_artwork else create_transparent_png(width, height)
    frame_path = os.path.join(assets_dir, "idle_1.png")
    with open(frame_path, "wb") as f:
        f.write(png_bytes)

    manifest = {
        "id": pkg_id,
        "name": "Test Pet",
        "species": "fox",
        "version": version,
        "size": {"width": width, "height": height},
        "default_animation": "idle",
        "allow_opaque": allow_opaque,
        "animations": {
            "idle": {
                "frames": ["assets/idle_1.png"],
                "fps": 4,
                "loop": True,
            }
        },
    }
    with open(os.path.join(pkg_root, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return pkg_root


# =========================================================================
# 1. Manifest Validation Tests
# =========================================================================

def test_validate_builtin_dog_and_cat():
    """Verify that existing built-in packages pass complete validation."""
    dog_res = validate_package("packages/pets/dog")
    assert dog_res.is_valid
    assert dog_res.package_id == "dog"
    assert dog_res.width == 160
    assert dog_res.height == 135

    cat_res = validate_package("packages/pets/cat")
    assert cat_res.is_valid
    assert cat_res.package_id == "cat"
    assert cat_res.width == 128
    assert cat_res.height == 128


def test_validate_manifest_missing_required_fields(tmp_path):
    """Manifest missing required fields raises PackageValidationError."""
    pkg_dir = tmp_path / "bad_pkg"
    pkg_dir.mkdir()
    manifest_path = pkg_dir / "manifest.json"

    # Missing animations
    manifest_path.write_text(json.dumps({
        "id": "bad", "name": "Bad", "species": "cat", "version": "1.0.0", "size": {"width": 64, "height": 64}
    }))
    with pytest.raises(PackageValidationError, match="missing required field: 'default_animation'"):
        validate_package_directory(str(pkg_dir))


def test_validate_manifest_invalid_semver(tmp_path):
    """Manifest with invalid semver format is rejected."""
    pkg = create_mock_package_dir(str(tmp_path), version="1.0")
    with pytest.raises(PackageValidationError, match="semantic versioning"):
        validate_package_directory(pkg)


def test_validate_manifest_invalid_id(tmp_path):
    """Manifest with invalid package ID containing special characters is rejected."""
    pkg = create_mock_package_dir(str(tmp_path), pkg_id="bad id!")
    with pytest.raises(PackageValidationError, match="Invalid package ID"):
        validate_package_directory(pkg)


def test_validate_manifest_invalid_size(tmp_path):
    """Manifest with non-positive dimensions is rejected."""
    pkg = create_mock_package_dir(str(tmp_path), width=64, height=64)
    mpath = os.path.join(pkg, "manifest.json")
    with open(mpath, "r") as f:
        data = json.load(f)
    data["size"] = {"width": -10, "height": 0}
    with open(mpath, "w") as f:
        json.dump(data, f)

    with pytest.raises(PackageValidationError, match="positive integers"):
        validate_package_directory(pkg)


def test_validate_manifest_missing_default_animation(tmp_path):
    """Manifest referencing non-existent default_animation is rejected."""
    pkg = create_mock_package_dir(str(tmp_path))
    mpath = os.path.join(pkg, "manifest.json")
    with open(mpath, "r") as f:
        data = json.load(f)
    data["default_animation"] = "dancing"
    with open(mpath, "w") as f:
        json.dump(data, f)

    with pytest.raises(PackageValidationError, match="default_animation 'dancing' is not defined"):
        validate_package_directory(pkg)


# =========================================================================
# 2. Image Decoding & Transparency Tests
# =========================================================================

def test_png_transparency_validation():
    """Verify alpha channel inspection distinguishes transparent from opaque images."""
    trans_img = Image.open(io.BytesIO(create_transparent_png()))
    assert validate_png_transparency(trans_img, allow_opaque=False) is True

    opaque_img = Image.open(io.BytesIO(create_opaque_png()))
    with pytest.raises(PackageValidationError, match="0 transparent pixels"):
        validate_png_transparency(opaque_img, allow_opaque=False)

    # When allow_opaque=True, opaque image is permitted
    assert validate_png_transparency(opaque_img, allow_opaque=True) is True


def test_package_validation_fails_on_opaque_artwork_without_flag(tmp_path):
    """Package with 100% opaque frame fails validation unless allow_opaque=True."""
    pkg = create_mock_package_dir(str(tmp_path), opaque_artwork=True, allow_opaque=False)
    with pytest.raises(PackageValidationError, match="0 transparent pixels"):
        validate_package_directory(pkg)

    # Now allow opaque
    pkg2 = create_mock_package_dir(str(tmp_path), pkg_id="pkg2", opaque_artwork=True, allow_opaque=True)
    res = validate_package_directory(pkg2)
    assert res.is_valid is True


def test_package_validation_fails_on_dimension_mismatch(tmp_path):
    """Frame image whose dimensions do not match manifest is rejected."""
    pkg = create_mock_package_dir(str(tmp_path), width=64, height=64)
    # Overwrite frame with 128x128 image
    frame_path = os.path.join(pkg, "assets", "idle_1.png")
    with open(frame_path, "wb") as f:
        f.write(create_transparent_png(128, 128))

    with pytest.raises(PackageValidationError, match="Dimension mismatch"):
        validate_package_directory(pkg)


def test_package_validation_fails_on_corrupted_image(tmp_path):
    """Corrupted frame file raises PackageValidationError."""
    pkg = create_mock_package_dir(str(tmp_path))
    frame_path = os.path.join(pkg, "assets", "idle_1.png")
    with open(frame_path, "wb") as f:
        f.write(b"NOT_A_PNG_HEADER")

    with pytest.raises(PackageValidationError, match="Corrupted or invalid image"):
        validate_package_directory(pkg)


# =========================================================================
# 3. Archive Security Tests
# =========================================================================

def test_archive_path_traversal_detection():
    """Sanitize detects ../, Windows drive letters, UNC, and control chars."""
    with pytest.raises(ArchiveSecurityError, match="Path traversal"):
        sanitize_and_validate_member_path("../evil.png")

    with pytest.raises(ArchiveSecurityError, match="Path traversal"):
        sanitize_and_validate_member_path("sub/../../evil.png")

    with pytest.raises(ArchiveSecurityError, match="Windows drive"):
        sanitize_and_validate_member_path("C:/evil.png")

    with pytest.raises(ArchiveSecurityError, match="UNC or network"):
        sanitize_and_validate_member_path("\\\\server\\share\\evil.png")

    with pytest.raises(ArchiveSecurityError, match="control character"):
        sanitize_and_validate_member_path("evil\x00name.png")

    with pytest.raises(ArchiveSecurityError, match="Prohibited file"):
        sanitize_and_validate_member_path("script.py")

    with pytest.raises(ArchiveSecurityError, match="Prohibited file"):
        sanitize_and_validate_member_path("pet/.git/config")


def test_archive_rejects_symlinks(tmp_path):
    """Tar archive containing symlinks is rejected."""
    tar_path = str(tmp_path / "symlink_attack.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        symlink_member = tarfile.TarInfo("evil_link.png")
        symlink_member.type = tarfile.SYMTYPE
        symlink_member.linkname = "/etc/passwd"
        tar.addfile(symlink_member)

    with pytest.raises(ArchiveSecurityError, match="Symlinks are prohibited"):
        validate_tar_archive(tar_path)


def test_archive_rejects_hardlinks(tmp_path):
    """Tar archive containing hard links is rejected."""
    tar_path = str(tmp_path / "hardlink_attack.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        link_member = tarfile.TarInfo("evil_hardlink.png")
        link_member.type = tarfile.LNKTYPE
        link_member.linkname = "manifest.json"
        tar.addfile(link_member)

    with pytest.raises(ArchiveSecurityError, match="Hard links are prohibited"):
        validate_tar_archive(tar_path)


def test_archive_rejects_duplicate_entries(tmp_path):
    """Archive with normalized duplicate entries is rejected."""
    zip_path = str(tmp_path / "dup.zip")
    with zipfile.ZipFile(zip_path, "w") as zf:
        zf.writestr("test/frame.png", create_transparent_png())
        zf.writestr("test//frame.png", create_transparent_png())

    with pytest.raises(ArchiveSecurityError, match="Duplicate entry"):
        validate_zip_archive(zip_path)


def test_archive_rejects_executable_files(tmp_path):
    """Archive containing executable script or binary is rejected."""
    tar_path = str(tmp_path / "evil_code.tar.gz")
    with tarfile.open(tar_path, "w:gz") as tar:
        py_data = b"print('hacked')"
        ti = tarfile.TarInfo("payload.py")
        ti.size = len(py_data)
        tar.addfile(ti, io.BytesIO(py_data))

    with pytest.raises(ArchiveSecurityError, match="Prohibited file"):
        validate_tar_archive(tar_path)


# =========================================================================
# 4. Package Export Tests
# =========================================================================

def test_export_package_tar_gz(tmp_path):
    """Export package to .tar.gz and verify clean contents and SHA-256."""
    export_dir = str(tmp_path / "exports")
    os.makedirs(export_dir, exist_ok=True)
    out_archive = os.path.join(export_dir, "dog_export.tar.gz")

    archive_path, sha256 = export_package("packages/pets/dog", output_path=out_archive, archive_format="tar.gz")
    assert os.path.isfile(archive_path)
    assert os.path.isfile(f"{archive_path}.sha256")
    assert compute_sha256(archive_path) == sha256

    # Verify independently valid
    val_res = validate_package(archive_path)
    assert val_res.is_valid
    assert val_res.package_id == "dog"


def test_export_package_zip(tmp_path):
    """Export package to .zip and verify clean contents and SHA-256."""
    export_dir = str(tmp_path / "exports")
    os.makedirs(export_dir, exist_ok=True)
    out_archive = os.path.join(export_dir, "cat_export.zip")

    archive_path, sha256 = export_package("packages/pets/cat", output_path=out_archive, archive_format="zip")
    assert os.path.isfile(archive_path)
    assert compute_sha256(archive_path) == sha256

    # Verify independently valid
    val_res = validate_package(archive_path)
    assert val_res.is_valid
    assert val_res.package_id == "cat"


def test_export_package_excludes_py_and_caches(tmp_path):
    """Export automatically filters out Python code and cache directories."""
    mock_dir = create_mock_package_dir(str(tmp_path), pkg_id="filter_test")
    # Pollute directory with malicious / dev files
    with open(os.path.join(mock_dir, "script.py"), "w") as f:
        f.write("# sneaky python file")
    pycache = os.path.join(mock_dir, "__pycache__")
    os.makedirs(pycache, exist_ok=True)
    with open(os.path.join(pycache, "dummy.pyc"), "wb") as f:
        f.write(b"junk")

    out_archive = str(tmp_path / "filter_test.tar.gz")
    archive_path, _ = export_package(mock_dir, output_path=out_archive)

    # Verify archive only contains manifest and frames, no .py or cache
    with tarfile.open(archive_path, "r:gz") as tar:
        names = tar.getnames()
        assert any("manifest.json" in n for n in names)
        assert not any(n.endswith(".py") for n in names)
        assert not any("__pycache__" in n for n in names)


# =========================================================================
# 5. Safe Installation & Rollback Tests
# =========================================================================

def test_install_package_atomic_and_safe(tmp_path):
    """Install a valid community package into target directory."""
    install_root = str(tmp_path / "user_pets")
    mock_pkg = create_mock_package_dir(str(tmp_path), pkg_id="fox")
    archive_path, _ = export_package(mock_pkg, output_path=str(tmp_path / "fox.tar.gz"))

    dest = install_package(archive_path, target_base_dir=install_root)
    assert os.path.isdir(dest)
    assert os.path.isfile(os.path.join(dest, "manifest.json"))

    # Verify permissions (0755 for dirs, 0644 for files)
    assert (os.stat(dest).st_mode & 0o777) == 0o755
    mfile = os.path.join(dest, "manifest.json")
    assert (os.stat(mfile).st_mode & 0o777) == 0o644

    # Verify discoverable via registry
    reg = PetRegistry(search_paths=[install_root])
    reg.discover()
    assert reg.get("fox") is not None


def test_install_package_already_installed_without_force(tmp_path):
    """Installing an already installed package without force=True raises PackageAlreadyInstalledError."""
    install_root = str(tmp_path / "user_pets")
    mock_pkg = create_mock_package_dir(str(tmp_path), pkg_id="fox")
    archive_path, _ = export_package(mock_pkg, output_path=str(tmp_path / "fox.tar.gz"))

    install_package(archive_path, target_base_dir=install_root)

    with pytest.raises(PackageAlreadyInstalledError, match="already installed"):
        install_package(archive_path, target_base_dir=install_root, force=False)


def test_install_package_force_replaces(tmp_path):
    """Installing with force=True safely replaces the package."""
    install_root = str(tmp_path / "user_pets")
    mock_pkg = create_mock_package_dir(str(tmp_path), pkg_id="fox", version="1.0.0")
    archive1, _ = export_package(mock_pkg, output_path=str(tmp_path / "fox1.tar.gz"))
    install_package(archive1, target_base_dir=install_root)

    # Create v1.1.0 update
    mock_pkg2 = create_mock_package_dir(str(tmp_path), pkg_id="fox", version="1.1.0")
    archive2, _ = export_package(mock_pkg2, output_path=str(tmp_path / "fox2.tar.gz"))
    dest = install_package(archive2, target_base_dir=install_root, force=True)

    with open(os.path.join(dest, "manifest.json"), "r") as f:
        data = json.load(f)
    assert data["version"] == "1.1.0"


def test_install_package_refuses_builtin_collision(tmp_path):
    """Refuse to install package colliding with built-in protected package."""
    install_root = str(tmp_path / "user_pets")
    # Export dog package
    archive_path, _ = export_package("packages/pets/dog", output_path=str(tmp_path / "dog.tar.gz"))

    with pytest.raises(BuiltinPackageCollisionError, match="Refusing to overwrite protected built-in"):
        install_package(archive_path, target_base_dir=install_root, builtin_paths=["packages/pets"])


def test_install_package_rollback_on_failure(tmp_path):
    """If replacement package is corrupted during install, original package is restored."""
    install_root = str(tmp_path / "user_pets")
    # 1. Install valid v1.0.0
    mock_pkg = create_mock_package_dir(str(tmp_path), pkg_id="panda", version="1.0.0")
    archive1, _ = export_package(mock_pkg, output_path=str(tmp_path / "panda1.tar.gz"))
    dest = install_package(archive1, target_base_dir=install_root)

    # 2. Create invalid archive with same ID (corrupted image)
    corrupted_pkg = create_mock_package_dir(str(tmp_path), pkg_id="panda", version="2.0.0")
    with open(os.path.join(corrupted_pkg, "assets", "idle_1.png"), "wb") as f:
        f.write(b"CORRUPTED_BYTES")

    bad_tar = str(tmp_path / "panda_bad.tar.gz")
    with tarfile.open(bad_tar, "w:gz") as tar:
        tar.add(corrupted_pkg, arcname="panda")

    # 3. Attempt forced update
    with pytest.raises(PackageValidationError):
        install_package(bad_tar, target_base_dir=install_root, force=True)

    # 4. Verify rollback: original v1.0.0 package is intact!
    assert os.path.isdir(dest)
    with open(os.path.join(dest, "manifest.json"), "r") as f:
        data = json.load(f)
    assert data["version"] == "1.0.0"


# =========================================================================
# 6. CLI Command Integration Tests
# =========================================================================

def test_cli_package_validate(capsys):
    """CLI validate succeeds on dog package."""
    ret = handle_package_cli(["validate", "packages/pets/dog"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Package Validation Succeeded" in captured.out
    assert "Corgi" in captured.out


def test_cli_package_export(tmp_path, capsys):
    """CLI export bundles package and outputs checksum."""
    out_file = str(tmp_path / "exported_dog.tar.gz")
    ret = handle_package_cli(["export", "dog", "--output", out_file])
    assert ret == 0
    assert os.path.isfile(out_file)
    captured = capsys.readouterr()
    assert "Successfully Exported Pet Package" in captured.out
    assert "SHA-256" in captured.out


def test_cli_package_install(tmp_path, capsys, monkeypatch):
    """CLI install validates and installs archive into user directory."""
    user_pets_dir = str(tmp_path / "user_pets")
    monkeypatch.setenv("CRITTER_USER_PETS_DIR", user_pets_dir)

    mock_pkg = create_mock_package_dir(str(tmp_path), pkg_id="comm_pet")
    out_file = str(tmp_path / "comm_pet.zip")
    export_package(mock_pkg, output_path=out_file, archive_format="zip")

    ret = handle_package_cli(["install", out_file, "--force"])
    assert ret == 0
    captured = capsys.readouterr()
    assert "Successfully Installed Pet Package" in captured.out
    assert os.path.isdir(os.path.join(user_pets_dir, "comm_pet"))
