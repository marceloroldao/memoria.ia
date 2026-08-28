import json
from pathlib import Path

from memoria_resolutiva.product_conversation import ConversationSemanticService
from memoria_resolutiva.product_evidence import ProductEvidenceService


def test_native_slice1_vectors_match_python_reference(tmp_path):
    data = json.loads((Path(__file__).parent / "fixtures" / "native_semantic_slice1.json").read_text("utf-8"))
    for case in data["cases"]:
        evidence = ProductEvidenceService.open(tmp_path / case["name"])
        service = ConversationSemanticService(evidence)
        ids = {}
        for source in case["sources"]:
            parents = [ids[p] for p in source.get("parent_memory_ids", [])]
            result = service.ingest(
                role=source["role"],
                text=source["text"],
                session_id=case["name"],
                order=source["order"],
                parent_memory_ids=parents,
            )
            ids[source["memory_id"]] = result.memory_ids[0]
        resolved = service.resolve(query=case["query"], session_id=case["name"])
        assert resolved.status == case["expected_status"], case["name"]
        assert resolved.selected_context == case["expected_context"], case["name"]
