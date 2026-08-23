from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import tempfile
import zipfile

from .product_service import EnterpriseMemoryService

BACKUP_FORMAT = "memoria.ia-enterprise-backup-v1"
BACKUP_MANIFEST = "backup.manifest.json"
PRODUCT_FILES = ("memory.snapshot", "enterprise.manifest.json")


@dataclass(frozen=True, slots=True)
class BackupValidation:
    valid: bool
    organization_id: str | None
    created_at: str | None
    files: tuple[str, ...]
    reason: str | None = None


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def create_backup(source_dir: str | os.PathLike[str], backup_path: str | os.PathLike[str]) -> Path:
    """Create a validated portable backup of the product memory state.

    The source is first loaded through EnterpriseMemoryService so an invalid or
    mismatched manifest/snapshot is never packaged as a successful backup.
    Product configuration and provider secrets are intentionally excluded.
    """

    source = Path(source_dir)
    service = EnterpriseMemoryService.load(source)
    files: dict[str, bytes] = {}
    for name in PRODUCT_FILES:
        path = source / name
        if not path.is_file():
            raise FileNotFoundError(f"required product state file is missing: {name}")
        files[name] = path.read_bytes()

    manifest = {
        "format": BACKUP_FORMAT,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "organization_id": service.organization.organization_id,
        "files": {
            name: {"sha256": _sha256(data), "size": len(data)}
            for name, data in files.items()
        },
        "includes_secrets": False,
    }
    manifest_bytes = json.dumps(manifest, indent=2, sort_keys=True).encode("utf-8") + b"\n"

    destination = Path(backup_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=destination.name + ".", suffix=".tmp", dir=destination.parent)
    os.close(fd)
    try:
        with zipfile.ZipFile(tmp_name, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(BACKUP_MANIFEST, manifest_bytes)
            for name in PRODUCT_FILES:
                archive.writestr(name, files[name])
        os.replace(tmp_name, destination)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)
    return destination


def validate_backup(backup_path: str | os.PathLike[str]) -> BackupValidation:
    path = Path(backup_path)
    try:
        with zipfile.ZipFile(path, "r") as archive:
            names = set(archive.namelist())
            allowed = {BACKUP_MANIFEST, *PRODUCT_FILES}
            if names != allowed:
                return BackupValidation(False, None, None, tuple(sorted(names)), "unexpected backup members")

            manifest = json.loads(archive.read(BACKUP_MANIFEST).decode("utf-8"))
            if manifest.get("format") != BACKUP_FORMAT:
                return BackupValidation(False, None, None, tuple(sorted(names)), "unsupported backup format")
            if manifest.get("includes_secrets") is not False:
                return BackupValidation(False, None, None, tuple(sorted(names)), "backup secret policy mismatch")

            file_meta = manifest.get("files")
            if not isinstance(file_meta, dict):
                return BackupValidation(False, None, None, tuple(sorted(names)), "invalid file metadata")
            for name in PRODUCT_FILES:
                meta = file_meta.get(name)
                if not isinstance(meta, dict):
                    return BackupValidation(False, None, None, tuple(sorted(names)), f"missing metadata for {name}")
                data = archive.read(name)
                if int(meta.get("size", -1)) != len(data):
                    return BackupValidation(False, None, None, tuple(sorted(names)), f"size mismatch for {name}")
                if not isinstance(meta.get("sha256"), str) or meta["sha256"] != _sha256(data):
                    return BackupValidation(False, None, None, tuple(sorted(names)), f"checksum mismatch for {name}")

            organization_id = manifest.get("organization_id")
            created_at = manifest.get("created_at")
            if not isinstance(organization_id, str) or not organization_id:
                return BackupValidation(False, None, None, tuple(sorted(names)), "missing organization identity")
            if not isinstance(created_at, str) or not created_at:
                return BackupValidation(False, organization_id, None, tuple(sorted(names)), "missing creation timestamp")
            return BackupValidation(True, organization_id, created_at, tuple(sorted(PRODUCT_FILES)))
    except (OSError, zipfile.BadZipFile, KeyError, ValueError, TypeError, json.JSONDecodeError) as exc:
        return BackupValidation(False, None, None, (), f"invalid backup: {exc}")


def restore_backup(
    backup_path: str | os.PathLike[str],
    target_dir: str | os.PathLike[str],
    *,
    expected_organization_id: str | None = None,
) -> EnterpriseMemoryService:
    """Validate and restore product memory state.

    Restore never extracts arbitrary archive paths. Only the two fixed product
    state files are read, checked and staged. A full EnterpriseMemoryService
    load is performed on the staged copy before target files are replaced.
    """

    validation = validate_backup(backup_path)
    if not validation.valid:
        raise ValueError(validation.reason or "backup validation failed")
    if expected_organization_id is not None and validation.organization_id != expected_organization_id:
        raise ValueError("backup organization does not match expected organization")

    target = Path(target_dir)
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="memoria-restore-") as tmp:
        stage = Path(tmp)
        with zipfile.ZipFile(backup_path, "r") as archive:
            for name in PRODUCT_FILES:
                _atomic_write(stage / name, archive.read(name))

        staged_service = EnterpriseMemoryService.load(stage)
        if staged_service.organization.organization_id != validation.organization_id:
            raise ValueError("backup manifest organization does not match product state")
        if expected_organization_id is not None and staged_service.organization.organization_id != expected_organization_id:
            raise ValueError("restored product state organization mismatch")

        for name in PRODUCT_FILES:
            _atomic_write(target / name, (stage / name).read_bytes())

    return EnterpriseMemoryService.load(target)
