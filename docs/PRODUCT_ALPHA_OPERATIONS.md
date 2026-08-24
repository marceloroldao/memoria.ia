# Memoria.ia Product Alpha — Operator Runbook

This runbook defines the canonical clean-host deployment and recovery path for the PC/server product alpha. It does not upgrade the product security status: the alpha remains `not-security-reviewed`.

## 1. Requirements

- Git
- Docker Engine with Docker Compose v2
- an unused TCP port 8080

No Python installation is required on the host for the canonical container path.

## 2. Clean installation

```bash
git clone https://github.com/marceloroldao/memoria.ia.git
cd memoria.ia
git checkout product/enterprise-alpha
cp .env.example .env
```

Edit `.env` and set at minimum a unique organization ID and a strong administrator credential. Keep provider API keys outside version control.

Start the service:

```bash
docker compose up -d --build
```

Verify health:

```bash
curl -fsS http://127.0.0.1:8080/api/v1/health
```

Open `http://127.0.0.1:8080/` for the minimal web UI.

## 3. Persistence check

Product state is stored in the named Docker volume `memoria-data`. `docker compose restart` and container replacement must retain the state as long as the volume is preserved.

Do not use `docker compose down -v` unless deletion of the persistent product state is intentional.

## 4. Backup

The backup contract includes only:

- `memory.snapshot`
- `enterprise.manifest.json`
- `backup.manifest.json` generated for the archive

Provider secrets and administrator/application plaintext credentials are not part of the backup contract.

For an operator-controlled backup, stop the service first so the volume is quiescent:

```bash
docker compose stop memoria
mkdir -p backups
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup" \
  memoria python scripts/product_backup.py create \
  --data-dir /data --output /backup/memoria-alpha.zip
docker compose start memoria
```

Validate without restoring:

```bash
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  memoria python scripts/product_backup.py validate \
  --backup /backup/memoria-alpha.zip
```

A valid archive reports `"valid": true`.

## 5. Restore to a clean volume

Stop the service and restore only into the intended organization. The expected organization check prevents accidentally loading another organization's state.

```bash
docker compose stop memoria
docker compose run --rm --no-deps \
  -v "$PWD/backups:/backup:ro" \
  memoria python scripts/product_backup.py restore \
  --backup /backup/memoria-alpha.zip \
  --data-dir /data \
  --organization-id "$MEMORIA_ORGANIZATION_ID"
docker compose start memoria
```

If the shell does not export `MEMORIA_ORGANIZATION_ID`, substitute the exact organization ID configured in `.env`.

After restore, verify `/api/v1/health`, authenticate to `/api/v1/admin/status`, and resolve a known memory record.

## 6. Recovery rules

- Never restore an archive that fails validation.
- Never bypass an organization mismatch.
- Keep `.env` and external-provider secrets out of backup archives and source control.
- Preserve at least one known-good backup outside the server being protected.
- Test restore, not only backup creation.
- Treat the alpha as a local/private deployment until a production security review is completed.

## 7. CI evidence

The `product-alpha validation` workflow is the executable clean-environment gate. It installs dependencies on Ubuntu, runs the full test suite, builds the container, starts the HTTP/UI service, persists a record, exercises the context comparison path, restarts on the same volume, resolves the prior record, and emits the machine-readable alpha acceptance artifact.

The workflow also performs an operator backup/validate/restore round trip into a fresh temporary data directory. A candidate product-alpha release must keep this gate green.
