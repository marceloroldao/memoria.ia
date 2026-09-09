from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import shutil

from .conversation_contract import ConversationService
from .epistemic_bdr_persistence import (
    EpistemicBDRStats,
    load_epistemic_audit_bdr,
    save_epistemic_audit_bdr,
)
from .evidence_state import EvidenceCorePersistence, EvidenceStateReceipt
from .topological_bdr_persistence import (
    BDRPersistenceStats,
    load_snapshot_bdr,
    save_snapshot_bdr,
)
from .topological_conversation_runtime import TopologicalConversationRuntime


_SCHEMA_VERSION = 1
_CURRENT_FILE = "CURRENT.json"
_MANIFEST_FILE = "generation.json"


@dataclass(frozen=True, slots=True)
class RuntimeCheckpoint:
    generation: int
    namespace: str
    evidence_receipt: EvidenceStateReceipt
    topology: BDRPersistenceStats
    epistemic: EpistemicBDRStats
    generation_dir: Path


class TopologicalRuntimePersistence:
    """Generation-safe persistence coordinator for the topological runtime.

    The existing storage formats remain authoritative:
    - EvidenceCorePersistence stores the complete source-evidence/reliability state;
    - memoria.topology.v1/* stores topological + temporal factual state;
    - memoria.epistemic.v1/* stores projection/learning/response-id audit.

    Cross-surface atomicity is achieved without inventing another storage schema:
    every checkpoint is written into a fresh generation directory and CURRENT.json
    is atomically replaced only after all three surfaces are durable and validated.
    A crash before pointer replacement therefore leaves the prior generation active.
    """

    def __init__(
        self,
        root: str | Path,
        *,
        atomic_library_path: str | Path,
        evidence_backend: str = "bdr",
        evidence_allow_fallback: bool = False,
    ) -> None:
        self.root = Path(root)
        self.atomic_library_path = Path(atomic_library_path)
        self.evidence_backend = evidence_backend
        self.evidence_allow_fallback = evidence_allow_fallback
        if not str(evidence_backend).strip():
            raise ValueError("evidence_backend must be non-empty")

    @property
    def current_path(self) -> Path:
        return self.root / _CURRENT_FILE

    def _read_current(self) -> dict[str, object] | None:
        if not self.current_path.exists():
            return None
        try:
            raw = json.loads(self.current_path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid topological runtime CURRENT pointer") from exc
        if not isinstance(raw, dict):
            raise ValueError("invalid topological runtime CURRENT pointer")
        if int(raw.get("schema_version", 0)) != _SCHEMA_VERSION:
            raise ValueError("unsupported topological runtime pointer schema version")
        generation = int(raw.get("generation", 0))
        directory = str(raw.get("generation_dir") or "").strip()
        if generation < 1 or not directory:
            raise ValueError("invalid topological runtime generation pointer")
        expected = f"generation-{generation:020d}"
        if directory != expected:
            raise ValueError("topological runtime pointer generation mismatch")
        return raw

    def _next_generation(self) -> int:
        current = self._read_current()
        return 1 if current is None else int(current["generation"]) + 1

    @staticmethod
    def _manifest_payload(checkpoint: RuntimeCheckpoint) -> dict[str, object]:
        return {
            "schema_version": _SCHEMA_VERSION,
            "generation": checkpoint.generation,
            "namespace": checkpoint.namespace,
            "evidence_receipt": checkpoint.evidence_receipt.as_dict(),
            "topology_bdr_sequence": checkpoint.topology.bdr_sequence,
            "epistemic_bdr_sequence": checkpoint.epistemic.bdr_sequence,
        }

    @staticmethod
    def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
            "utf-8",
        )
        tmp.replace(path)

    def checkpoint(self, runtime: TopologicalConversationRuntime) -> RuntimeCheckpoint:
        self.root.mkdir(parents=True, exist_ok=True)
        generation = self._next_generation()
        final_dir = self.root / f"generation-{generation:020d}"
        staging_dir = self.root / f".generation-{generation:020d}.tmp"
        if final_dir.exists():
            raise ValueError("target runtime generation already exists")
        if staging_dir.exists():
            shutil.rmtree(staging_dir)
        staging_dir.mkdir(parents=True)

        try:
            evidence_persistence = EvidenceCorePersistence(
                staging_dir / "evidence",
                backend=self.evidence_backend,
                allow_fallback=self.evidence_allow_fallback,
            )
            evidence_receipt = evidence_persistence.store(runtime.evidence)

            cognitive_root = staging_dir / "cognitive"
            topology = save_snapshot_bdr(
                cognitive_root,
                self.atomic_library_path,
                runtime.addresses,
                runtime.store,
            )
            epistemic = save_epistemic_audit_bdr(
                cognitive_root,
                self.atomic_library_path,
                runtime.bridge,
                runtime.gate,
                runtime.validator,
            )

            checkpoint = RuntimeCheckpoint(
                generation=generation,
                namespace=runtime.namespace,
                evidence_receipt=evidence_receipt,
                topology=topology,
                epistemic=epistemic,
                generation_dir=final_dir,
            )
            self._write_json_atomic(staging_dir / _MANIFEST_FILE, self._manifest_payload(checkpoint))
            staging_dir.replace(final_dir)
            self._write_json_atomic(
                self.current_path,
                {
                    "schema_version": _SCHEMA_VERSION,
                    "generation": generation,
                    "generation_dir": final_dir.name,
                },
            )
            return checkpoint
        except Exception:
            if staging_dir.exists():
                shutil.rmtree(staging_dir, ignore_errors=True)
            raise

    def open(self, conversation: ConversationService) -> TopologicalConversationRuntime:
        current = self._read_current()
        if current is None:
            raise FileNotFoundError("topological runtime has no committed generation")
        generation = int(current["generation"])
        generation_dir = self.root / str(current["generation_dir"])
        manifest_path = generation_dir / _MANIFEST_FILE
        try:
            manifest = json.loads(manifest_path.read_text("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid topological runtime generation manifest") from exc
        if not isinstance(manifest, dict):
            raise ValueError("invalid topological runtime generation manifest")
        if int(manifest.get("schema_version", 0)) != _SCHEMA_VERSION:
            raise ValueError("unsupported topological runtime generation schema version")
        if int(manifest.get("generation", 0)) != generation:
            raise ValueError("runtime generation manifest does not match CURRENT")
        namespace = str(manifest.get("namespace") or "").strip()
        if not namespace:
            raise ValueError("runtime generation namespace must be non-empty")

        receipt_raw = manifest.get("evidence_receipt")
        if not isinstance(receipt_raw, dict):
            raise ValueError("runtime generation is missing EvidenceCore receipt")
        evidence_receipt = EvidenceStateReceipt(
            backend=str(receipt_raw["backend"]),
            state_id=str(receipt_raw["state_id"]),
            sha256=str(receipt_raw["sha256"]),
        )
        evidence = EvidenceCorePersistence(
            generation_dir / "evidence",
            backend=evidence_receipt.backend,
            allow_fallback=False,
        ).load(evidence_receipt)

        addresses, store = load_snapshot_bdr(
            generation_dir / "cognitive",
            self.atomic_library_path,
        )
        runtime = TopologicalConversationRuntime(
            conversation,
            evidence=evidence,
            addresses=addresses,
            store=store,
            namespace=namespace,
        )
        epistemic = load_epistemic_audit_bdr(
            generation_dir / "cognitive",
            self.atomic_library_path,
            runtime.bridge,
            runtime.gate,
            runtime.validator,
        )

        expected_topology_sequence = int(manifest.get("topology_bdr_sequence", 0))
        expected_epistemic_sequence = int(manifest.get("epistemic_bdr_sequence", 0))
        if expected_topology_sequence < 1 or expected_epistemic_sequence < expected_topology_sequence:
            raise ValueError("invalid runtime generation BDR sequence metadata")
        if epistemic.bdr_sequence < expected_epistemic_sequence:
            raise ValueError("runtime epistemic BDR sequence regressed after restart")
        return runtime
