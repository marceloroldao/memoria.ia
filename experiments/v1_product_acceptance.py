from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from fastapi.testclient import TestClient

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_evidence import ProductEvidenceService, attach_evidence_routes
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import OrganizationIdentity
from memoria_resolutiva.product_persistence import ProductSnapshotPersistence, PersistentEnterpriseMemoryService


PASS = "PASS"
FAIL = "FAIL"


def _check(name: str, ok: bool, evidence: dict | str) -> dict:
    return {"criterion": name, "status": PASS if ok else FAIL, "evidence": evidence}


def run_acceptance(*, backend: str = "sqlite", turns: int = 40) -> dict:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        allow_fallback = backend != "bdr"
        persistence = ProductSnapshotPersistence(root / "persistence", backend=backend, allow_fallback=allow_fallback)
        service = PersistentEnterpriseMemoryService(
            OrganizationIdentity("v1-acceptance", "V1 Acceptance"),
            persistence=persistence,
        )
        evidence = ProductEvidenceService.open(root / "evidence", backend=backend, allow_fallback=allow_fallback)
        chat = ProductChatService(service, MockLLMAdapter())
        app = create_app(service, api_key="acceptance-key", data_dir=root, chat_service=chat)
        attach_evidence_routes(app, api_key="acceptance-key", service=evidence)
        client = TestClient(app)
        headers = {"X-Memoria-Key": "acceptance-key"}

        checks: list[dict] = []
        total_started = perf_counter()
        chat_metrics: list[dict] = []

        for turn in range(turns):
            key = f"asset.{turn % 8}.state"
            payload = {"turn": turn, "state": "active" if turn % 3 else "standby"}
            response = client.post("/api/v1/memories", headers=headers, json={
                "knowledge_id": f"k-{turn}",
                "key": key,
                "payload": payload,
                "provenance": f"acceptance-turn-{turn}",
            })
            if response.status_code == 409:
                response = client.put(f"/api/v1/memories/{key}", headers=headers, json={
                    "payload": payload,
                    "provenance": f"acceptance-update-{turn}",
                })
            if response.status_code not in (200, 201):
                checks.append(_check("long-session writes", False, {"turn": turn, "status": response.status_code}))
                break
            if turn % 4 == 0:
                c = client.post("/api/v1/chat", headers=headers, json={
                    "message": f"read {key}",
                    "mode": "memoria",
                    "memory_keys": [key],
                })
                if c.status_code == 200:
                    chat_metrics.append(c.json().get("metrics", {}))
        else:
            checks.append(_check("long-session writes", True, {"turns": turns, "logical_keys": 8}))

        final_expected: dict[str, object] = {}
        for i in range(8):
            key = f"asset.{i}.state"
            r = client.post("/api/v1/memories/resolve", headers=headers, json={"key": key})
            if r.status_code == 200 and r.json().get("hit"):
                final_expected[key] = r.json()["record"]["payload"]
        checks.append(_check("long-session retrieval", len(final_expected) == 8, {"resolved_keys": len(final_expected)}))

        evidence_rows = [
            ("Delta", "powers", "controller", "e1", "sensor-a", "lab-a"),
            ("controller", "belongs_to", "Orion", "e2", "registry-b", "lab-a"),
            ("Delta", "powers", "other-controller", "e3", "sensor-c", "lab-b"),
        ]
        for subject, predicate, obj, eid, origin, namespace in evidence_rows:
            rr = client.post("/api/v1/evidence/relations", headers=headers, json={
                "subject": subject,
                "predicate": predicate,
                "object": obj,
                "evidence_id": eid,
                "source_text": f"{subject} {predicate} {obj}",
                "origin": origin,
                "namespace": namespace,
                "confidence": 0.9,
            })
            if rr.status_code != 201:
                checks.append(_check("evidence ingest", False, {"status": rr.status_code, "body": rr.text[:200]}))
                break
        else:
            checks.append(_check("evidence ingest", True, {"relations": len(evidence_rows)}))

        inferred = client.post("/api/v1/evidence/infer", headers=headers, json={
            "source": "Delta", "target": "Orion", "namespace": "lab-a", "max_hops": 2
        })
        isolated = client.post("/api/v1/evidence/infer", headers=headers, json={
            "source": "Delta", "target": "Orion", "namespace": "lab-b", "max_hops": 2
        })
        checks.append(_check(
            "evidence inference and namespace isolation",
            inferred.status_code == 200 and inferred.json().get("inferred") is True
            and isolated.status_code == 200 and isolated.json().get("inferred") is False,
            {
                "lab_a": inferred.json() if inferred.status_code == 200 else None,
                "lab_b": isolated.json() if isolated.status_code == 200 else None,
            },
        ))

        compare = client.post("/api/v1/chat/compare", headers=headers, json={
            "message": "summarize the current state of asset 0",
            "baseline_context": ["irrelevant historical context " * 80, json.dumps(final_expected, sort_keys=True)],
            "memory_keys": ["asset.0.state"],
        })
        compare_json = compare.json() if compare.status_code == 200 else {}
        checks.append(_check(
            "baseline-vs-memoria comparison",
            compare.status_code == 200 and compare_json.get("token_reduction") is not None,
            compare_json,
        ))

        restarted = PersistentEnterpriseMemoryService.load(
            root,
            persistence=ProductSnapshotPersistence(root / "persistence", backend=backend, allow_fallback=allow_fallback),
        )
        restarted_evidence = ProductEvidenceService.open(
            root / "evidence",
            backend=backend,
            allow_fallback=allow_fallback,
        )
        app2 = create_app(
            restarted,
            api_key="acceptance-key",
            data_dir=root,
            chat_service=ProductChatService(restarted, MockLLMAdapter()),
        )
        attach_evidence_routes(app2, api_key="acceptance-key", service=restarted_evidence)
        client2 = TestClient(app2)

        restart_ok = True
        for key, expected in final_expected.items():
            r = client2.post("/api/v1/memories/resolve", headers=headers, json={"key": key})
            restart_ok = restart_ok and r.status_code == 200 and r.json().get("hit") and r.json()["record"]["payload"] == expected
        checks.append(_check("memory restart equivalence", restart_ok, {"keys_checked": len(final_expected)}))

        inferred2 = client2.post("/api/v1/evidence/infer", headers=headers, json={
            "source": "Delta", "target": "Orion", "namespace": "lab-a", "max_hops": 2
        })
        checks.append(_check(
            "evidence restart equivalence",
            inferred2.status_code == 200 and inferred2.json().get("inferred") is True,
            inferred2.json() if inferred2.status_code == 200 else {},
        ))

        health = client2.get("/api/v1/health")
        evidence_health = client2.get("/api/v1/evidence/health", headers=headers)
        checks.append(_check(
            "health endpoints",
            health.status_code == 200 and evidence_health.status_code == 200,
            {
                "product": health.json() if health.status_code == 200 else None,
                "evidence": evidence_health.json() if evidence_health.status_code == 200 else None,
            },
        ))

        totals = {
            "chat_calls": len(chat_metrics),
            "memory_hits": sum(int(m.get("memory_hits", 0)) for m in chat_metrics),
            "memory_misses": sum(int(m.get("memory_misses", 0)) for m in chat_metrics),
            "retrieved_context_chars": sum(int(m.get("retrieved_context_chars", 0)) for m in chat_metrics),
            "input_tokens": sum(int(m.get("input_tokens", 0)) for m in chat_metrics),
            "output_tokens": sum(int(m.get("output_tokens", 0)) for m in chat_metrics),
            "external_calls": sum(int(m.get("external_calls", 0)) for m in chat_metrics),
            "memory_latency_ms": sum(float(m.get("memory_latency_ms", 0.0)) for m in chat_metrics),
            "llm_latency_ms": sum(float(m.get("llm_latency_ms", 0.0)) for m in chat_metrics),
        }
        counts = {
            PASS: sum(1 for c in checks if c["status"] == PASS),
            FAIL: sum(1 for c in checks if c["status"] == FAIL),
        }
        return {
            "acceptance": "memoria.ia-v1-candidate-product-acceptance",
            "backend": backend,
            "turns": turns,
            "overall": PASS if counts[FAIL] == 0 else FAIL,
            "counts": counts,
            "checks": checks,
            "metrics": totals,
            "compare": compare_json,
            "elapsed_ms": (perf_counter() - total_started) * 1000.0,
            "notes": [
                "Mock LLM validates the provider-neutral product path and measurements; it does not prove external-provider availability.",
                "MA2A is intentionally outside this acceptance gate.",
            ],
        }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=("sqlite", "bdr"), default="sqlite")
    parser.add_argument("--turns", type=int, default=40)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-fail", action="store_true")
    args = parser.parse_args()
    report = run_acceptance(backend=args.backend, turns=args.turns)
    rendered = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")
    if args.fail_on_fail and report["overall"] != PASS:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
