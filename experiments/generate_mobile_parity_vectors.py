from __future__ import annotations

import argparse
import json
from pathlib import Path
import tempfile

from memoria_resolutiva.episodic_recall import Episode, EpisodicRecallService
from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def _conversation_result(result):
    return {
        "status": result.status,
        "confidence": result.confidence,
        "memory_ids": list(result.memory_ids),
        "selected_context": result.selected_context,
        "relations": list(result.relations),
        "provenance": list(result.provenance),
    }


def _episode_result(result):
    return {
        "status": result.status,
        "confidence": result.confidence,
        "episode_ids": list(result.episode_ids),
        "selected_context": result.selected_context,
        "order": result.order,
        "timestamp": result.timestamp,
        "event_type": result.event_type,
        "topics": list(result.topics),
        "source_type": result.source_type,
        "source_authority": result.source_authority,
        "ultimate_source_memory_id": result.ultimate_source_memory_id,
    }


def build_vectors() -> dict:
    with tempfile.TemporaryDirectory(prefix="memoria-mobile-vectors-") as tmp:
        evidence = ProductEvidenceService.open(Path(tmp) / "evidence", backend="sqlite")
        conv = ConversationSemanticService(evidence)
        episodes = EpisodicRecallService(evidence.core)

        s1 = "semantic-basic"
        learned = conv.ingest(
            role="user",
            text="O servidor Atlas é Norte.",
            session_id=s1,
            order=1,
            timestamp="2026-08-28T10:00:00Z",
        )
        semantic_hit = conv.resolve(query="Qual servidor é Norte?", session_id=s1)
        semantic_miss = conv.resolve(query="Qual é a temperatura do oceano?", session_id=s1)

        s2 = "provenance-loop"
        source = conv.ingest(
            role="user",
            text="Meu código de teste é 4729.",
            session_id=s2,
            order=1,
            timestamp="2026-08-28T10:10:00Z",
        )
        source_id = source.memory_ids[0]
        for order in range(2, 7):
            conv.ingest(
                role="assistant",
                text="Seu código de teste é 4729.",
                session_id=s2,
                order=order,
                timestamp=f"2026-08-28T10:{8 + order:02d}:00Z",
                parent_memory_ids=(source_id,),
            )
        provenance_hit = conv.resolve(query="Qual é meu código de teste?", session_id=s2)

        s3 = "semantic-ambiguous"
        conv.ingest(role="user", text="Atlas é Norte.", session_id=s3, order=1)
        conv.ingest(role="user", text="Atlas é Sul.", session_id=s3, order=2)
        semantic_ambiguous = conv.resolve(query="Atlas é qual?", session_id=s3)

        s4 = "episodic"
        episodes.record(Episode(
            episode_id="episode-old",
            role="assistant",
            text="Resumo antigo do projeto Orion.",
            namespace=s4,
            order=1,
            timestamp="2026-08-28T11:00:00Z",
            event_type="summary",
            topics=("orion",),
        ))
        episodes.record(Episode(
            episode_id="episode-new",
            role="assistant",
            text="Resumo mais recente do projeto Orion.",
            namespace=s4,
            order=9,
            timestamp="2026-08-28T11:09:00Z",
            event_type="summary",
            topics=("orion",),
        ))
        episodic_latest = episodes.recall_latest(
            query="Qual foi o último resumo do Orion?",
            namespace=s4,
            role="assistant",
            event_type="summary",
            topics=("orion",),
        )

        s5 = "episodic-ambiguous"
        episodes.record(Episode("note-a", "assistant", "Nota alfa.", s5, 5, None, "note", ()))
        episodes.record(Episode("note-b", "assistant", "Nota beta.", s5, 5, None, "note", ()))
        episodic_ambiguous = episodes.recall_latest(
            query="Qual foi a última nota?",
            namespace=s5,
            role="assistant",
            event_type="note",
        )

        evidence.save()
        reopened = ProductEvidenceService.open(Path(tmp) / "evidence", backend="sqlite")
        restart_conv = ConversationSemanticService(reopened)
        restart_episodes = EpisodicRecallService(reopened.core)

        return {
            "schema": "memoria-mobile-parity-v1",
            "reference": "python-v1-candidate",
            "vectors": [
                {
                    "id": "semantic.basic.hit",
                    "kind": "conversation",
                    "expected": _conversation_result(semantic_hit),
                    "learned_memory_ids": list(learned.memory_ids),
                },
                {
                    "id": "semantic.open_set.unresolved",
                    "kind": "conversation",
                    "expected": _conversation_result(semantic_miss),
                },
                {
                    "id": "semantic.independent_conflict.unresolved",
                    "kind": "conversation",
                    "expected": _conversation_result(semantic_ambiguous),
                },
                {
                    "id": "provenance.echoes.canonical_source",
                    "kind": "conversation",
                    "expected": _conversation_result(provenance_hit),
                    "expected_ultimate_source_memory_id": source_id,
                },
                {
                    "id": "episodic.latest.hit",
                    "kind": "episode",
                    "expected": _episode_result(episodic_latest),
                },
                {
                    "id": "episodic.same_order.unresolved",
                    "kind": "episode",
                    "expected": _episode_result(episodic_ambiguous),
                },
                {
                    "id": "restart.semantic.same_result",
                    "kind": "conversation",
                    "expected": _conversation_result(restart_conv.resolve(query="Qual servidor é Norte?", session_id=s1)),
                    "equals_vector": "semantic.basic.hit",
                },
                {
                    "id": "restart.episodic.same_result",
                    "kind": "episode",
                    "expected": _episode_result(restart_episodes.recall_latest(
                        query="Qual foi o último resumo do Orion?",
                        namespace=s4,
                        role="assistant",
                        event_type="summary",
                        topics=("orion",),
                    )),
                    "equals_vector": "episodic.latest.hit",
                },
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = build_vectors()
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, "utf-8")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
