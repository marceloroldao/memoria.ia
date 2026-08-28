from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _result_payload(result):
    return {
        "status": result.status,
        "confidence": round(float(result.confidence), 6),
        "memory_ids": list(result.memory_ids),
        "selected_context": result.selected_context,
        "provenance": list(result.provenance),
    }


def build_vectors() -> list[dict]:
    vectors: list[dict] = []

    with TemporaryDirectory() as tmp:
        evidence = ProductEvidenceService.open(Path(tmp) / "evidence")
        svc = ConversationSemanticService(evidence)
        learned = svc.ingest(
            role="user",
            text="Minha fonte principal é 24 V.",
            session_id="power",
            order=1,
        )
        query = "Qual é a fonte principal?"
        vectors.append({
            "name": "user-source-hit",
            "session_id": "power",
            "turns": [{"role": "user", "text": "Minha fonte principal é 24 V.", "order": 1}],
            "query": query,
            "expected": _result_payload(svc.resolve(query=query, session_id="power")),
            "learned_memory_ids": list(learned.memory_ids),
        })

    with TemporaryDirectory() as tmp:
        evidence = ProductEvidenceService.open(Path(tmp) / "evidence")
        svc = ConversationSemanticService(evidence)
        first = svc.ingest(role="user", text="Atlas é norte.", session_id="ambiguity", order=1)
        second = svc.ingest(role="user", text="Atlas é sul.", session_id="ambiguity", order=2)
        query = "Atlas é onde?"
        vectors.append({
            "name": "independent-conflict-unresolved",
            "session_id": "ambiguity",
            "turns": [
                {"role": "user", "text": "Atlas é norte.", "order": 1},
                {"role": "user", "text": "Atlas é sul.", "order": 2},
            ],
            "query": query,
            "expected": _result_payload(svc.resolve(query=query, session_id="ambiguity")),
            "learned_memory_ids": [*first.memory_ids, *second.memory_ids],
        })

    with TemporaryDirectory() as tmp:
        evidence = ProductEvidenceService.open(Path(tmp) / "evidence")
        svc = ConversationSemanticService(evidence)
        source = svc.ingest(role="user", text="Projeto Atlas é norte.", session_id="echo", order=1)
        root_id = source.memory_ids[0]
        svc.ingest(
            role="assistant",
            text="Projeto Atlas é norte.",
            session_id="echo",
            order=2,
            parent_memory_ids=(root_id,),
        )
        query = "Projeto Atlas é onde?"
        vectors.append({
            "name": "assistant-echo-does-not-replace-root",
            "session_id": "echo",
            "turns": [
                {"role": "user", "text": "Projeto Atlas é norte.", "order": 1},
                {"role": "assistant", "text": "Projeto Atlas é norte.", "order": 2, "parent_memory_ids": [root_id]},
            ],
            "query": query,
            "expected": _result_payload(svc.resolve(query=query, session_id="echo")),
            "learned_memory_ids": list(source.memory_ids),
        })

    return vectors


def main() -> None:
    out = Path("tests/fixtures/mobile_semantic_parity_v1.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(build_vectors(), ensure_ascii=False, indent=2, sort_keys=True) + "\n", "utf-8")
    print(out)


if __name__ == "__main__":
    main()
