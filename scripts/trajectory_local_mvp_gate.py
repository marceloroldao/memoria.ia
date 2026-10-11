#!/usr/bin/env python3
"""Synthetic public fixtures over real HTTP, process restart and closed backup.

Retrieval references belong to this evaluator, never to the learner/API request.
Reports preserve semantic failures; no result is a qualified factual answer.
"""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time

import httpx


@contextmanager
def server(library, directory, key):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    env = dict(os.environ, MEMORIA_API_KEY=key)
    root = Path(__file__).resolve().parents[1]
    env["PYTHONPATH"] = str(root / "src") + os.pathsep + env.get("PYTHONPATH", "")
    process = subprocess.Popen([sys.executable, str(root / "scripts/trajectory_local_mvp.py"),
        "--library", str(library.resolve()), "--data-dir", str(directory), "--port", str(port)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    client = httpx.Client(base_url=f"http://127.0.0.1:{port}", headers={"X-Memoria-Key": key}, timeout=10, trust_env=False)
    try:
        deadline = time.monotonic() + 15
        while True:
            if process.poll() is not None:
                raise RuntimeError("local server exited before accepting requests")
            try:
                if client.get("/").status_code == 200:
                    break
            except httpx.TransportError:
                pass
            if time.monotonic() >= deadline:
                raise RuntimeError("local server startup timed out")
            time.sleep(0.05)
        yield client
    finally:
        client.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def check_response(response):
    response.raise_for_status()
    return response.json()


def gate(library):
    checks, cases = {}, []
    key = secrets.token_hex(24)
    with tempfile.TemporaryDirectory(prefix="memoria-local-mvp-") as temporary:
        state, backup = Path(temporary) / "state", Path(temporary) / "backup"
        with server(library, state, key) as c:
            checks["http_ui"] = "Uma memória" in c.get("/").text
            checks["auth_rejects"] = c.get("/api/entries", headers={"X-Memoria-Key": "wrong"}).status_code == 401
            for scope, text, kind in [
                ("nomes", "Meu gato se chama Alt.", "user_turn"),
                ("nomes", "Meu gato se chama Bia.", "user_turn"),
                ("nomes", "Meu gato se chama Alt.", "user_turn"),
                ("nomes", "Meu gato dorme no sofa.", "user_turn"),
                ("nomes", "Meu gato se chama Cadu.", "assistant_generated"),
                ("outra", "Meu gato se chama Duda.", "user_turn"),
                ("agenda", "Minha reunião está marcada para terça-feira.", "user_turn"),
                ("agenda", "Minha viagem está marcada para sexta-feira.", "user_turn"),
                ("gerada", "Minha cidade é Recife.", "assistant_generated"),
            ]:
                result = check_response(c.post("/api/entries", json=dict(scope=scope, text=text, source_kind=kind)))
                assert result["persisted"]
            before = check_response(c.get("/api/entries", params={"scope": "nomes"}))
            queries = [
                ("nomes", "Qual nome do meu gato?", {"Meu gato se chama Alt.", "Meu gato se chama Bia."}),
                ("nomes", "Qual a cor do meu gato?", set()),
                ("agenda", "Quando é minha reunião?", {"Minha reunião está marcada para terça-feira."}),
                ("agenda", "Qual dia é minha viagem?", {"Minha viagem está marcada para sexta-feira."}),
                ("nomes", "zzzzzzz", set()),
                ("vazia", "Qual nome do meu gato?", set()),
                ("gerada", "Minha cidade é Recife.", set()),
            ]
            views = []
            for scope, text, expected in queries:
                result = check_response(c.post("/api/query", json=dict(scope=scope, text=text)))
                views.append(result)
                observed = {r["text"] for r in result["candidates"]}
                cases.append(dict(scope=scope, query=text, expected=sorted(expected), retrieved=sorted(observed),
                    missing=sorted(expected-observed), extra=sorted(observed-expected),
                    exact_retrieval_set=observed == expected, status=result["status"]))
            after = check_response(c.get("/api/entries", params={"scope": "nomes"}))
            checks["query_read_only"] = before == after
            checks["always_unqualified"] = all(v["answer"] is None and v["qualified"] is False
                and v["selected_target"] is None and v["selection_used"] is False and v["query_recorded"] is False for v in views)
            origins = [o for v in views for r in v["candidates"] for o in r["origins"]]
            checks["generated_origins_excluded"] = all(o["source_kind"] != "assistant_generated" for o in origins)
            checks["scope_preserved"] = all(o["hierarchy_id"] == "conversation:mvp:" + v["scope"]
                for v in views for r in v["candidates"] for o in r["origins"])
            checks["duplicates_addressable"] = any(r["text"] == "Meu gato se chama Alt." and len(r["origins"]) == 2 for r in views[0]["candidates"])
            checks["competing_names_retained"] = {"Meu gato se chama Alt.", "Meu gato se chama Bia."} <= {r["text"] for r in views[0]["candidates"]}
        shutil.copytree(state, backup)  # Only after process termination / native close.
        for directory, prefix in [(state, "restart"), (backup, "closed_backup_restore")]:
            with server(library, directory, key) as c:
                cold = [check_response(c.post("/api/query", json=dict(scope=scope, text=text))) for scope, text, _ in queries]
                checks[prefix + "_full_view_equal"] = cold == views
                checks[prefix + "_history_equal"] = check_response(c.get("/api/entries", params={"scope": "nomes"})) == before
    passed = sum(checks.values())
    exact = sum(case["exact_retrieval_set"] for case in cases)
    return dict(format="memoria.ia-local-mvp-http-gate-v1", integrity_status="PASS" if passed == len(checks) else "FAIL",
        integrity_passed=passed, integrity_total=len(checks), checks=checks, cases=cases,
        retrieval_exact_cases=exact, retrieval_total_cases=len(cases),
        retrieval_quality_status="PASS_CURATED_CASES_ONLY" if exact == len(cases) else "FAIL_EXTRA_OR_MISSING_CONTENT",
        factual_quality_status="NOT_EVALUATED", answer_generation=False,
        fixture_scope="public synthetic examples; not a general natural-language benchmark")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = gate(args.library)
    body = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(body, encoding="utf-8")
    print(body, end="")
    raise SystemExit(0 if result["integrity_status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
