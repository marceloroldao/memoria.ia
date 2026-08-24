from __future__ import annotations

import argparse
import json
from pathlib import Path

from memoria_resolutiva.product_backup import create_backup, restore_backup, validate_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="Memoria.ia product-alpha backup/restore operator utility")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create", help="create a validated product-state backup")
    create.add_argument("--data-dir", required=True)
    create.add_argument("--output", required=True)

    validate = sub.add_parser("validate", help="validate a backup without restoring it")
    validate.add_argument("--backup", required=True)

    restore = sub.add_parser("restore", help="restore a validated product-state backup")
    restore.add_argument("--backup", required=True)
    restore.add_argument("--data-dir", required=True)
    restore.add_argument("--organization-id")

    args = parser.parse_args()
    if args.command == "create":
        path = create_backup(args.data_dir, args.output)
        validation = validate_backup(path)
        print(json.dumps({
            "created": str(Path(path)),
            "valid": validation.valid,
            "organization_id": validation.organization_id,
            "includes_secrets": False,
        }, sort_keys=True))
        return 0 if validation.valid else 2

    if args.command == "validate":
        validation = validate_backup(args.backup)
        print(json.dumps({
            "valid": validation.valid,
            "organization_id": validation.organization_id,
            "created_at": validation.created_at,
            "files": list(validation.files),
            "reason": validation.reason,
        }, sort_keys=True))
        return 0 if validation.valid else 2

    service = restore_backup(
        args.backup,
        args.data_dir,
        expected_organization_id=args.organization_id,
    )
    print(json.dumps({
        "restored": True,
        "organization_id": service.organization.organization_id,
        "data_dir": str(Path(args.data_dir)),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
