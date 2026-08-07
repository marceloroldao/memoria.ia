from dataclasses import dataclass
import hashlib


def digest_payload(payload: bytes, layer: int) -> str:
    h = hashlib.blake2b(digest_size=16)
    h.update(layer.to_bytes(2, "big"))
    h.update(payload)
    return h.hexdigest()


@dataclass(frozen=True, slots=True)
class Node:
    node_id: str
    layer: int
    payload: bytes
