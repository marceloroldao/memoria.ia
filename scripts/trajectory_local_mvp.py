#!/usr/bin/env python3
"""Opt-in local memory UI; persistent native observations, read-only queries.

This prototype does not change the product server or qualify inferred answers.
Run one Linux process per data directory. See docs/trajectory-local-mvp.md.
"""
from __future__ import annotations

import argparse
from contextlib import asynccontextmanager
import ctypes
import fcntl
from hashlib import sha256
import hmac
import os
from pathlib import Path
import re
import threading
from typing import Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from mobile_region_replay import NativeProbe
from trajectory_copy_relation_probe import copy_relations
from trajectory_window_consistency_probe import WindowChanged, window_snapshot


class LocalNative(NativeProbe):
    def open(self):
        status = self.lib.memoria_mobile_open(
            str(self.data_dir).encode(), b"trajectory-local-mvp",
            ctypes.byref(self.handle))
        if status != 0:
            raise RuntimeError("native open failed")


class ScopedRequest(BaseModel):
    scope: str = Field(default="principal", pattern=r"^[a-zA-Z0-9_-]{1,64}$")

    @property
    def region(self):
        return "conversation:mvp:" + self.scope


class TextRequest(ScopedRequest):
    text: str = Field(min_length=1, max_length=20000)

    @field_validator("text")
    @classmethod
    def nonempty(cls, value):
        if not value.strip():
            raise ValueError("text must contain non-whitespace characters")
        return value  # Preserve exact raw text and addressability.


class ObserveRequest(TextRequest):
    source_kind: Literal["user_turn", "assistant_generated"] = "user_turn"


class QueryRequest(TextRequest):
    text: str = Field(min_length=1, max_length=4000)
    experimental: bool = False


class BoundedWindow:
    def __init__(self, native):
        self.native = native

    def call(self, name, request):
        status, value = self.native.call(name, request)
        if value.get("window_revision", 0) > 4096:
            raise HTTPException(413, "Memória excede o limite local de 4096 entradas; nenhuma análise parcial foi feita.")
        return status, value


def create_app(*, library: Path, data_dir: Path, api_key: str) -> FastAPI:
    if not api_key or not api_key.strip():
        raise ValueError("MEMORIA_API_KEY is required")
    lock = threading.RLock()

    @asynccontextmanager
    async def lifespan(app):
        data_dir.mkdir(parents=True, exist_ok=True)
        owner = (data_dir / "mvp.lock").open("a")
        native = None
        try:
            fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            native_dir = data_dir / "native"
            native_dir.mkdir(exist_ok=True)
            native = LocalNative(library, native_dir)
            app.state.native = native
            app.state.lock = lock
            yield
        finally:
            try:
                if native is not None:
                    if native.lib.memoria_mobile_flush(native.handle) != 0:
                        raise RuntimeError("native flush failed")
            finally:
                if native is not None:
                    native.close()
                owner.close()

    app = FastAPI(title="Memoria.ia — MVP local experimental", lifespan=lifespan)

    def authorize(x_memoria_key: str = Header(default="")):
        if not hmac.compare_digest(x_memoria_key.encode(), api_key.encode()):
            raise HTTPException(401, "Chave inválida")

    def snapshot(region):
        try:
            user = window_snapshot(BoundedWindow(app.state.native), region)
            generated = window_snapshot(BoundedWindow(app.state.native), region + ":generated")
            rows = sorted(user["rows"] + generated["rows"], key=lambda r: (r["sequence"], r["source_id"]))
            if len(rows) > 4096:
                raise HTTPException(413, "Memória excede o limite local de 4096 entradas")
            token = sha256((user["token"] + generated["token"]).encode()).hexdigest()
            return dict(rows=rows, revision=len(rows), token=token)
        except WindowChanged:
            raise HTTPException(409, "Memória mudou durante a leitura; tente novamente.") from None

    def verify(region, before):
        after = snapshot(region)
        if before != after:
            raise HTTPException(409, "Memória mudou durante a consulta; tente novamente.")

    @app.get("/", response_class=HTMLResponse)
    def index():
        return Path(__file__).with_suffix(".html").read_text(encoding="utf-8")

    @app.get("/api/entries", dependencies=[Depends(authorize)])
    def entries(scope: str = "principal"):
        # Reuse the same namespace validation for GET requests.
        if not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", scope):
            raise HTTPException(422, "Nome de memória inválido")
        with lock:
            view = snapshot(ScopedRequest(scope=scope).region)
            return dict(scope=scope, entries=view["rows"], revision=view["revision"])

    @app.post("/api/entries", status_code=201, dependencies=[Depends(authorize)])
    def observe(request: ObserveRequest):
        with lock:
            before = snapshot(request.region)
            if len(before["rows"]) >= 4096:
                raise HTTPException(413, "Limite local de entradas atingido")
            # Persist generated content in its own native field. It must not
            # train the legacy recall field even if results are later filtered.
            storage_region = request.region + (":generated" if request.source_kind == "assistant_generated" else "")
            row = dict(hierarchy_id=storage_region, source_id="local:" + uuid4().hex,
                       sequence=1 + max((r["sequence"] for r in before["rows"]), default=0),
                       text=request.text, source_kind=request.source_kind)
            status, result = app.state.native.call("observe_structural_text", row)
            if status != 0 or result.get("duplicate"):
                raise HTTPException(500, "Registro nativo rejeitado")
            if app.state.native.lib.memoria_mobile_flush(app.state.native.handle) != 0:
                raise HTTPException(500, "Não foi possível confirmar a persistência")
            return dict(entry=row, persisted=True)

    @app.post("/api/query", dependencies=[Depends(authorize)])
    def query(request: QueryRequest):
        with lock:
            before = snapshot(request.region)
            rows = before["rows"]
            accepted = [r for r in rows if r["source_kind"] != "assistant_generated"]
            if request.experimental and (len(rows) > 64 or sum(len(r["text"]) for r in rows) > 4096):
                raise HTTPException(413, "Hipóteses experimentais limitadas a 64 entradas e 4096 caracteres; consulta comum continua disponível.")
            status, recall = app.state.native.call("resolve_structural_text", dict(
                hierarchy_id=request.region, query=request.text, top_k=16))
            if status not in (0, 2) or recall.get("status") not in ("HIT", "UNRESOLVED"):
                raise HTTPException(500, "Consulta nativa rejeitada")
            texts = list(dict.fromkeys([r["text"] for r in accepted if r["text"] == request.text] +
                [c["source_text"] for c in recall.get("contexts", [])]))
            candidates = []
            for text in texts:
                origins = [dict(hierarchy_id=r["hierarchy_id"], source_id=r["source_id"],
                                sequence=r["sequence"], source_kind=r["source_kind"])
                           for r in accepted if r["text"] == text]
                if origins:
                    candidates.append(dict(text=text, origins=origins,
                        evidence_kind="EXACT_OBSERVED_CONTENT" if text == request.text else "NATIVE_STRUCTURAL_RECALL"))
            # Generated rows are timeline barriers only in the experimental
            # adapter; their actual native storage address stays in the journal.
            experimental_rows = [dict(r, hierarchy_id=request.region) if r["source_kind"] == "assistant_generated" else r for r in rows]
            experiment = copy_relations(experimental_rows, request.region, request.text) if request.experimental else None
            verify(request.region, before)
            return dict(scope=request.scope, status="CANDIDATES" if candidates else "UNRESOLVED",
                        candidates=candidates, experimental=experiment,
                        answer=None, qualified=False, selected_target=None, selection_used=False,
                        query_recorded=False, revision=before["revision"], window_token=before["token"],
                        recall_limit=16, factual_quality_status="NOT_EVALUATED")

    return app


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8787)
    args = parser.parse_args()
    import uvicorn
    uvicorn.run(create_app(library=args.library, data_dir=args.data_dir,
                          api_key=os.environ.get("MEMORIA_API_KEY", "")),
                host="127.0.0.1", port=args.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
