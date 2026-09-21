from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from .persistent_address_trajectory_v2 import PersistentAddressTrajectoryStoreV2


class V2TrajectoryIngestRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    session_id: str | None = Field(default=None, max_length=256)


def attach_v2_trajectory_routes(
    app: FastAPI,
    *,
    api_key: str,
    store: PersistentAddressTrajectoryStoreV2,
) -> None:
    """Attach explicitly experimental V2 trajectory ingestion/health routes.

    Resolution is exposed through the product-level /api/v1/resolve/native route;
    these endpoints only provide the experimental ingestion boundary needed to feed
    the same persisted trajectory store without involving an LLM.
    """

    def require_admin(x_memoria_key: str | None = Header(default=None)) -> None:
        if x_memoria_key is None or not hmac.compare_digest(x_memoria_key, api_key):
            raise HTTPException(status_code=401, detail="invalid API credentials")

    @app.get("/api/v1/v2/trajectory/health", dependencies=[Depends(require_admin)])
    def v2_trajectory_health():
        return {
            "status": "ok",
            "capability": "address-trajectory-v2",
            "backend": store.backend,
            "llm_required": False,
        }

    @app.post(
        "/api/v1/v2/trajectory/ingest",
        status_code=201,
        dependencies=[Depends(require_admin)],
    )
    def v2_trajectory_ingest(request: V2TrajectoryIngestRequest):
        trajectory = store.ingest(request.text, session_id=request.session_id)
        return {
            "stored": True,
            "trajectory_id": trajectory.trajectory_id,
            "session_id": request.session_id,
            "address_count": len(trajectory.addresses),
            "backend": store.backend,
        }
