from __future__ import annotations

import io
import json
from pathlib import Path
import zipfile

import pytest

from memoria_resolutiva.product_backup import (
    BACKUP_MANIFEST,
    create_backup,
    restore_backup,
    validate_backup,
)
from memoria_resolutiva.product_identity import MemoryScope, OrganizationIdentity
from memoria_resolutiva.product_service import EnterpriseMemoryService


def _seed_service(root: Path, organization_id: str = "backup-org") -> EnterpriseMemoryService:
    service = EnterpriseMemoryService(OrganizationIdentity(organization_id, "Backup Org"))
    scope = MemoryScope(organization_id)
    service.remember(scope, "fact-1", {"value": "survives"}, ("key", "backup.fact"))
    service.save(root)
    return service


def test_create_validate_restore_round_trip(tmp_path: Path):
    source = tmp_path / "source"
    _seed_service(source)
    backup = create_backup(source, tmp_path / "state.mia-backup")

    validation = validate_backup(backup)
    assert validation.valid is True
    assert validation.organization_id == "backup-org"
    assert set(validation.files) == {"memory.snapshot", "enterprise.manifest.json"}

    target = tmp_path / "restored"
    restored = restore_backup(backup, target, expected_organization_id="backup-org")
    record = restored.recall(MemoryScope("backup-org"), ("key", "backup.fact"))
    assert record is not None
    assert record.payload == {"value": "survives"}


def test_backup_excludes_product_secrets(tmp_path: Path):
    source = tmp_path / "source"
    _seed_service(source)
    (source / "product-secrets.json").write_text('{"OPENAI_API_KEY":"must-not-leak"}', "utf-8")
    backup = create_backup(source, tmp_path / "state.mia-backup")

    with zipfile.ZipFile(backup, "r") as archive:
        assert "product-secrets.json" not in archive.namelist()
        manifest = json.loads(archive.read(BACKUP_MANIFEST))
        assert manifest["includes_secrets"] is False
        assert b"must-not-leak" not in Path(backup).read_bytes()


def test_tampered_backup_is_rejected_before_restore(tmp_path: Path):
    source = tmp_path / "source"
    _seed_service(source)
    backup = create_backup(source, tmp_path / "state.mia-backup")

    tampered = tmp_path / "tampered.mia-backup"
    with zipfile.ZipFile(backup, "r") as original, zipfile.ZipFile(tampered, "w") as changed:
        for name in original.namelist():
            data = original.read(name)
            if name == "memory.snapshot":
                data = data + b"tamper"
            changed.writestr(name, data)

    validation = validate_backup(tampered)
    assert validation.valid is False
    assert "mismatch" in (validation.reason or "")

    with pytest.raises(ValueError):
        restore_backup(tampered, tmp_path / "restore-target")


def test_restore_rejects_wrong_organization(tmp_path: Path):
    source = tmp_path / "source"
    _seed_service(source, "org-a")
    backup = create_backup(source, tmp_path / "state.mia-backup")

    with pytest.raises(ValueError, match="organization"):
        restore_backup(backup, tmp_path / "target", expected_organization_id="org-b")


def test_backup_with_unexpected_member_is_rejected(tmp_path: Path):
    source = tmp_path / "source"
    _seed_service(source)
    backup = create_backup(source, tmp_path / "state.mia-backup")

    expanded = tmp_path / "expanded.mia-backup"
    with zipfile.ZipFile(backup, "r") as original, zipfile.ZipFile(expanded, "w") as changed:
        for name in original.namelist():
            changed.writestr(name, original.read(name))
        changed.writestr("../unexpected.txt", b"no")

    validation = validate_backup(expanded)
    assert validation.valid is False
    assert validation.reason == "unexpected backup members"
