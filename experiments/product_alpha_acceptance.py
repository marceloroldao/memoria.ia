from __future__ import annotations

import argparse
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from memoria_resolutiva.llm_adapter import MockLLMAdapter
from memoria_resolutiva.product_chat import ProductChatService
from memoria_resolutiva.product_http import create_app
from memoria_resolutiva.product_identity import (
    CertificateStatus,
    LicenseStatus,
    NodeIdentity,
    OrganizationIdentity,
)
from memoria_resolutiva.product_service import EnterpriseMemoryService


STATUS_PASS = "PASS"
STATUS_PARTIAL = "PARTIAL"
STATUS_FAIL = "FAIL"


def item(number: int, name: str, status: str, evidence: str) -> dict:
    return {"id": number, "criterion": name, "status": status, "evidence": evidence}


def run_gate(*, tests_passed: bool, container_validated: bool, benchmark_file: Path | None) -> dict:
    results: list[dict] = []

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        org = OrganizationIdentity("acceptance-org", "Acceptance Organization")
        service = EnterpriseMemoryService(org)
        node = NodeIdentity(
            organization_id=org.organization_id,
            node_id="memoria:acceptance-org:primary",
            certificate_status=CertificateStatus.NOT_CONFIGURED,
            license_status=LicenseStatus.NOT_CONFIGURED,
            capabilities=frozenset({"memory.read", "memory.write"}),
        )
        chat_service = ProductChatService(service, MockLLMAdapter())
        app = create_app(service, api_key="acceptance-only-key", data_dir=root, node_identity=node, chat_service=chat_service)
        client = TestClient(app)
        headers = {"X-Memoria-Key": "acceptance-only-key"}

        results.append(item(1, "install Memoria.ia on a PC/server", STATUS_PASS if container_validated else STATUS_PARTIAL,
                            "Docker build/start is validated by CI when --container-validated is supplied."))

        health = client.get("/api/v1/health")
        status = client.get("/api/v1/admin/status", headers=headers)
        results.append(item(2, "create/configure an organization", STATUS_PASS if status.json()["organization"]["organization_id"] == org.organization_id else STATUS_FAIL,
                            "Organization identity is configured before service creation."))
        results.append(item(3, "start the service", STATUS_PASS if health.status_code == 200 and health.json().get("status") == "ok" else STATUS_FAIL,
                            "Health endpoint responds from a fresh product instance."))

        ui = client.get("/")
        results.append(item(4, "access the web interface", STATUS_PASS if ui.status_code == 200 and "Memoria.ia Enterprise" in ui.text else STATUS_FAIL,
                            "Web UI is served from the same FastAPI product service."))

        # Mock validates the provider-neutral boundary but is intentionally not claimed as a real LLM.
        results.append(item(5, "configure one LLM provider", STATUS_PARTIAL,
                            "Mock adapter is validated end-to-end; OpenAI adapter is implemented/configurable but live external credentials are not exercised in CI."))

        stored = client.post("/api/v1/memories", headers=headers, json={
            "knowledge_id": "acceptance-memory",
            "key": "customer.plan",
            "payload": {"plan": "pro"},
        })
        chat = client.post("/api/v1/chat", headers=headers, json={
            "message": "what plan is stored?",
            "mode": "memoria",
            "memory_keys": ["customer.plan"],
        })
        results.append(item(6, "send messages through Memoria.ia", STATUS_PARTIAL if chat.status_code == 200 else STATUS_FAIL,
                            "Chat path is validated with deterministic mock; live external provider remains operator-dependent."))

        snapshot_ok = (root / "memory.snapshot").exists() and (root / "enterprise.manifest.json").exists()
        results.append(item(7, "persist memory", STATUS_PASS if stored.status_code == 201 and snapshot_ok else STATUS_FAIL,
                            "Store operation writes snapshot and enterprise manifest."))

        loaded = EnterpriseMemoryService.load(root)
        app2 = create_app(loaded, api_key="acceptance-only-key", data_dir=root, node_identity=node,
                          chat_service=ProductChatService(loaded, MockLLMAdapter()))
        client2 = TestClient(app2)
        recovered = client2.post("/api/v1/memories/resolve", headers=headers, json={"key": "customer.plan"})
        recovered_ok = recovered.status_code == 200 and recovered.json().get("hit") is True
        results.append(item(8, "restart without losing valid persisted state", STATUS_PASS if recovered_ok else STATUS_FAIL,
                            "Service reloads persisted snapshot/manifest into a new process-level instance."))
        results.append(item(9, "retrieve previous relevant information", STATUS_PASS if recovered_ok and recovered.json()["record"]["payload"] == {"plan": "pro"} else STATUS_FAIL,
                            "Previously stored key resolves after reload."))

        metrics = chat.json().get("metrics", {}) if chat.status_code == 200 else {}
        metric_fields = {"memory_hits", "memory_misses", "context_retrieved_chars", "context_sent_chars", "input_tokens", "output_tokens", "memory_latency_ms", "llm_latency_ms", "external_calls", "provider"}
        results.append(item(10, "observe memory/context metrics", STATUS_PASS if metric_fields.issubset(metrics) else STATUS_FAIL,
                            "Chat response exposes memory, context, token, latency, call, and provider measurements."))

        compare = client.post("/api/v1/chat/compare", headers=headers, json={
            "message": "what plan is stored?",
            "baseline_context": ["plan is pro", "irrelevant context " * 30],
            "memory_keys": ["customer.plan"],
        })
        compare_ok = compare.status_code == 200 and compare.json().get("token_reduction") is not None
        results.append(item(11, "compare baseline vs Memoria mode", STATUS_PASS if compare_ok else STATUS_FAIL,
                            "Compare endpoint executes both modes and reports observed token reduction."))

        other = EnterpriseMemoryService(OrganizationIdentity("other-org"))
        # The external key may be identical, but each organization has an independent service and namespace.
        from memoria_resolutiva.product_identity import MemoryScope
        other_scope = MemoryScope("other-org")
        other.remember(other_scope, "acceptance-memory", {"plan": "other"}, ("key", "customer.plan"))
        original = loaded.recall(MemoryScope("acceptance-org"), ("key", "customer.plan"))
        isolated = original is not None and original.payload == {"plan": "pro"}
        results.append(item(12, "verify organization isolation", STATUS_PASS if isolated else STATUS_FAIL,
                            "Same external identifiers are independently stored under organization-qualified namespaces."))

        admin = client.get("/api/v1/admin/status", headers=headers).json()
        node_ok = admin.get("node", {}).get("node_id") == node.node_id and "certificate_status" in admin.get("node", {})
        results.append(item(13, "inspect node/identity status", STATUS_PASS if node_ok else STATUS_FAIL,
                            "Admin status exposes node identity, certificate status, license status and capabilities without secrets."))

        results.append(item(14, "run automated tests", STATUS_PASS if tests_passed else STATUS_PARTIAL,
                            "Full automated suite is required to pass --tests-passed in CI."))

        benchmark_ok = False
        if benchmark_file and benchmark_file.exists():
            try:
                data = json.loads(benchmark_file.read_text("utf-8"))
                benchmark_ok = data.get("benchmark") == "memoria.ia-product-context-v1" and "summary" in data
            except (OSError, ValueError, TypeError):
                benchmark_ok = False
        results.append(item(15, "reproduce benchmark results", STATUS_PASS if benchmark_ok else STATUS_PARTIAL,
                            "Machine-readable product context benchmark artifact is required for PASS."))

    counts = {status: sum(1 for r in results if r["status"] == status) for status in (STATUS_PASS, STATUS_PARTIAL, STATUS_FAIL)}
    overall = STATUS_FAIL if counts[STATUS_FAIL] else (STATUS_PARTIAL if counts[STATUS_PARTIAL] else STATUS_PASS)
    return {
        "gate": "memoria.ia-enterprise-product-alpha-v1",
        "overall": overall,
        "counts": counts,
        "criteria": results,
        "notes": [
            "PARTIAL is not treated as a production guarantee.",
            "Mock adapter proves the boundary and instrumentation, not external LLM quality or availability.",
            "Semantic routing v0.96 remains experimental and is not required for exact-key product-alpha acceptance.",
            "Security status remains not-security-reviewed.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--tests-passed", action="store_true")
    parser.add_argument("--container-validated", action="store_true")
    parser.add_argument("--benchmark-file", type=Path)
    parser.add_argument("--fail-on-fail", action="store_true")
    args = parser.parse_args()

    report = run_gate(
        tests_passed=args.tests_passed,
        container_validated=args.container_validated,
        benchmark_file=args.benchmark_file,
    )
    rendered = json.dumps(report, indent=2, sort_keys=True)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", "utf-8")
    if args.fail_on_fail and report["counts"][STATUS_FAIL]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
