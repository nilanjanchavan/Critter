"""Archive security validation and extraction defenses for Critter pet packages.

Guards against:
- Zip-slip and path traversal (../, ..\\, Windows drive paths, UNC paths)
- Special archive entries (symlinks, hard links, FIFOs, devices)
- Null bytes and control characters
- Duplicate normalized paths
- Archive decompression bombs (file count, total size, individual size limits)
- Executable files (.py, .sh, binaries) and dangerous hidden files (.git, .env)
- Untrusted archive permissions
"""

import os
import posixpath
import re
import tarfile
from typing import Dict, List, Optional, Set, Tuple
import zipfile

# --- Resource Limits ---
MAX_ARCHIVE_SIZE_BYTES = 50 * 1024 * 1024        # 50 MB
MAX_UNCOMPRESSED_TOTAL_BYTES = 100 * 1024 * 1024  # 100 MB
MAX_FILE_COUNT = 500
MAX_INDIVIDUAL_FILE_BYTES = 10 * 1024 * 1024      # 10 MB

# --- Explicit Allowlist & Ban Lists ---
PERMITTED_FILE_EXTENSIONS: Set[str] = {
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".md",
    ".txt",
    ".license",
}

BANNED_FILE_PATTERNS = [
    re.compile(r"\.(py|pyc|pyo|pyd|sh|bash|exe|dll|so|bin|elf|bat|cmd|vbs|ps1|msi)$", re.IGNORECASE),
    re.compile(r"(^|/)(__pycache__|\.git|\.env|\.bashrc|\.profile|\.ssh|\.DS_Store|Thumbs\.db)($|/)", re.IGNORECASE),
]

CONTROL_CHARS_REGEX = re.compile(r"[\x00-\x1f\x7f]")
WINDOWS_DRIVE_REGEX = re.compile(r"^[a-zA-Z]:")
UNC_PATH_REGEX = re.compile(r"^\\\\[^\\]+\\[^\\]+")


class ArchiveSecurityError(Exception):
    """Raised when an archive member violates security policies."""


def sanitize_and_validate_member_path(raw_path: str, is_dir: bool = False) -> str:
    """Validate archive member path against path-traversal, UNC, and control character attacks.

    Returns the normalized relative POSIX path.
    Raises ArchiveSecurityError if path is unsafe.
    """
    if not raw_path:
        raise ArchiveSecurityError("Empty member path in archive")

    # Check for null bytes and control characters
    if CONTROL_CHARS_REGEX.search(raw_path):
        raise ArchiveSecurityError(f"Member path contains null byte or control character: {raw_path!r}")

    # Check for Windows drive letter (e.g. C:...)
    if WINDOWS_DRIVE_REGEX.search(raw_path):
        raise ArchiveSecurityError(f"Windows drive letter prohibited in path: {raw_path}")

    # Check for UNC path (e.g. \\server\share)
    if UNC_PATH_REGEX.search(raw_path) or raw_path.startswith("//") or raw_path.startswith("\\\\"):
        raise ArchiveSecurityError(f"UNC or network paths prohibited in archive: {raw_path}")

    # Normalize backslashes to forward slashes
    posix_path = raw_path.replace("\\", "/")

    # Check for absolute path
    if posix_path.startswith("/"):
        raise ArchiveSecurityError(f"Absolute paths prohibited in archive: {raw_path}")

    # Check for path traversal components
    parts = [p for p in posix_path.split("/") if p and p != "."]
    if ".." in parts:
        raise ArchiveSecurityError(f"Path traversal ('..') detected in path: {raw_path}")

    normalized = posixpath.normpath(posix_path)
    if normalized.startswith("..") or normalized == "." or normalized == "":
        raise ArchiveSecurityError(f"Normalized path escapes package root: {raw_path}")

    # Check banned filenames and extensions
    basename = posixpath.basename(normalized)
    for banned_pat in BANNED_FILE_PATTERNS:
        if banned_pat.search(normalized):
            raise ArchiveSecurityError(f"Prohibited file or directory pattern in archive: {normalized}")

    # If it's a file (not directory), check extension allowlist
    if not is_dir and not raw_path.endswith("/"):
        _, ext = posixpath.splitext(basename)
        ext_lower = ext.lower()
        if ext_lower not in PERMITTED_FILE_EXTENSIONS:
            # Allow common documentation files without extensions (e.g., LICENSE)
            if basename.upper() not in {"LICENSE", "README", "AUTHORS"}:
                raise ArchiveSecurityError(
                    f"File extension '{ext}' not in permitted allowlist {sorted(PERMITTED_FILE_EXTENSIONS)}: {normalized}"
                )

    return normalized


def validate_tar_archive(tar_path: str) -> List[Tuple[tarfile.TarInfo, str]]:
    """Scan and validate a .tar (.tar.gz, .tar.bz2, .tar.xz) archive.

    Returns a list of (tarinfo, sanitized_path) tuples.
    Raises ArchiveSecurityError if any member violates constraints.
    """
    archive_size = os.path.getsize(tar_path)
    if archive_size > MAX_ARCHIVE_SIZE_BYTES:
        raise ArchiveSecurityError(
            f"Archive size ({archive_size} bytes) exceeds limit ({MAX_ARCHIVE_SIZE_BYTES} bytes)"
        )

    try:
        tar = tarfile.open(tar_path, "r:*")
    except Exception as exc:
        raise ArchiveSecurityError(f"Corrupted or invalid tar archive: {exc}") from exc

    validated_members: List[Tuple[tarfile.TarInfo, str]] = []
    seen_paths: Set[str] = set()
    total_uncompressed_bytes = 0
    file_count = 0

    with tar:
        for member in tar.getmembers():
            # Check special file types
            if member.issym():
                raise ArchiveSecurityError(f"Symlinks are prohibited in pet packages: {member.name} -> {member.linkname}")
            if member.islnk():
                raise ArchiveSecurityError(f"Hard links are prohibited in pet packages: {member.name} -> {member.linkname}")
            if member.isdev() or member.ischr() or member.isblk() or member.isfifo():
                raise ArchiveSecurityError(f"Special device or FIFO entries prohibited in archive: {member.name}")

            if not (member.isreg() or member.isdir()):
                raise ArchiveSecurityError(f"Unsupported tar entry type for member: {member.name}")

            is_dir = member.isdir() or member.name.endswith("/")
            sanitized_path = sanitize_and_validate_member_path(member.name, is_dir=is_dir)

            # Detect normalized duplicate entries
            if sanitized_path in seen_paths:
                raise ArchiveSecurityError(f"Duplicate entry detected in archive: {sanitized_path}")
            seen_paths.add(sanitized_path)

            if member.isreg():
                file_count += 1
                if file_count > MAX_FILE_COUNT:
                    raise ArchiveSecurityError(f"Archive exceeds maximum file count limit ({MAX_FILE_COUNT})")

                if member.size > MAX_INDIVIDUAL_FILE_BYTES:
                    raise ArchiveSecurityError(
                        f"File '{sanitized_path}' size ({member.size} bytes) exceeds individual limit ({MAX_INDIVIDUAL_FILE_BYTES} bytes)"
                    )

                total_uncompressed_bytes += member.size
                if total_uncompressed_bytes > MAX_UNCOMPRESSED_TOTAL_BYTES:
                    raise ArchiveSecurityError(
                        f"Total uncompressed size ({total_uncompressed_bytes} bytes) exceeds decompression bomb limit ({MAX_UNCOMPRESSED_TOTAL_BYTES} bytes)"
                    )

            validated_members.append((member, sanitized_path))

    return validated_members


def validate_zip_archive(zip_path: str) -> List[Tuple[zipfile.ZipInfo, str]]:
    """Scan and validate a .zip archive.

    Returns a list of (zipinfo, sanitized_path) tuples.
    Raises ArchiveSecurityError if any member violates constraints.
    """
    archive_size = os.path.getsize(zip_path)
    if archive_size > MAX_ARCHIVE_SIZE_BYTES:
        raise ArchiveSecurityError(
            f"Archive size ({archive_size} bytes) exceeds limit ({MAX_ARCHIVE_SIZE_BYTES} bytes)"
        )

    try:
        zf = zipfile.ZipFile(zip_path, "r")
    except Exception as exc:
        raise ArchiveSecurityError(f"Corrupted or invalid zip archive: {exc}") from exc

    validated_members: List[Tuple[zipfile.ZipInfo, str]] = []
    seen_paths: Set[str] = set()
    total_uncompressed_bytes = 0
    file_count = 0

    with zf:
        for info in zf.infolist():
            # Check for symlink attribute in ZIP (UNIX mode 0120000)
            unix_mode = info.external_attr >> 16
            if (unix_mode & 0o170000) == 0o120000:
                raise ArchiveSecurityError(f"Symlinks are prohibited in pet packages: {info.filename}")

            is_dir = info.is_dir() or info.filename.endswith("/")
            sanitized_path = sanitize_and_validate_member_path(info.filename, is_dir=is_dir)

            if sanitized_path in seen_paths:
                raise ArchiveSecurityError(f"Duplicate entry detected in archive: {sanitized_path}")
            seen_paths.add(sanitized_path)
            if not is_dir:
                file_count += 1
                if file_count > MAX_FILE_COUNT:
                    raise ArchiveSecurityError(f"Archive exceeds maximum file count limit ({MAX_FILE_COUNT})")

                if info.file_size > MAX_INDIVIDUAL_FILE_BYTES:
                    raise ArchiveSecurityError(
                        f"File '{sanitized_path}' size ({info.file_size} bytes) exceeds individual limit ({MAX_INDIVIDUAL_FILE_BYTES} bytes)"
                    )

                total_uncompressed_bytes += info.file_size
                if total_uncompressed_bytes > MAX_UNCOMPRESSED_TOTAL_BYTES:
                    raise ArchiveSecurityError(
                        f"Total uncompressed size ({total_uncompressed_bytes} bytes) exceeds decompression bomb limit ({MAX_UNCOMPRESSED_TOTAL_BYTES} bytes)"
                    )

            validated_members.append((info, sanitized_path))

    return validated_members


def safe_extract_tar(tar_path: str, destination_dir: str) -> None:
    """Safely extract validated tar archive into destination directory enforcing safe permissions."""
    validated = validate_tar_archive(tar_path)
    os.makedirs(destination_dir, exist_ok=True)
    abs_dest = os.path.abspath(destination_dir)

    with tarfile.open(tar_path, "r:*") as tar:
        for member, rel_path in validated:
            target_path = os.path.abspath(os.path.join(abs_dest, rel_path))
            # Verify strictly inside destination
            if os.path.commonpath([abs_dest, target_path]) != abs_dest:
                raise ArchiveSecurityError(f"Extraction path escapes destination: {rel_path}")

            if member.isdir():
                os.makedirs(target_path, mode=0o755, exist_ok=True)
                os.chmod(target_path, 0o755)
            elif member.isreg():
                parent = os.path.dirname(target_path)
                os.makedirs(parent, mode=0o755, exist_ok=True)
                with tar.extractfile(member) as src_f, open(target_path, "wb") as dst_f:
                    while chunk := src_f.read(65536):
                        dst_f.write(chunk)
                # Never trust archive permissions; set safe 0644
                os.chmod(target_path, 0o644)


def safe_extract_zip(zip_path: str, destination_dir: str) -> None:
    """Safely extract validated zip archive into destination directory enforcing safe permissions."""
    validated = validate_zip_archive(zip_path)
    os.makedirs(destination_dir, exist_ok=True)
    abs_dest = os.path.abspath(destination_dir)

    with zipfile.ZipFile(zip_path, "r") as zf:
        for info, rel_path in validated:
            target_path = os.path.abspath(os.path.join(abs_dest, rel_path))
            if os.path.commonpath([abs_dest, target_path]) != abs_dest:
                raise ArchiveSecurityError(f"Extraction path escapes destination: {rel_path}")

            is_dir = info.is_dir() or info.filename.endswith("/")
            if is_dir:
                os.makedirs(target_path, mode=0o755, exist_ok=True)
                os.chmod(target_path, 0o755)
            else:
                parent = os.path.dirname(target_path)
                os.makedirs(parent, mode=0o755, exist_ok=True)
                with zf.open(info) as src_f, open(target_path, "wb") as dst_f:
                    while chunk := src_f.read(65536):
                        dst_f.write(chunk)
                os.chmod(target_path, 0o644)
