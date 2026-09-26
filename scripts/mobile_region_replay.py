#!/usr/bin/env python3
"""Replay a private OFF.IA export against the native read-only region probes.

Input texts and raw responses are never printed or stored by this script.
Only aggregate counts and addressability checks are emitted as JSON.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import tempfile
from collections import Counter
from pathlib import Path


class Buffer(ctypes.Structure):
    _fields_ = [("data", ctypes.POINTER(ctypes.c_uint8)), ("size", ctypes.c_size_t)]


class NativeProbe:
    def __init__(self, library: Path, data_dir: Path) -> None:
        self.lib = ctypes.CDLL(str(library.resolve()))
        self.lib.memoria_mobile_open.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.POINTER(ctypes.c_void_p)
        ]
        self.lib.memoria_mobile_open.restype = ctypes.c_int
        self.lib.memoria_mobile_close.argtypes = [ctypes.c_void_p]
        self.lib.memoria_mobile_flush.argtypes = [ctypes.c_void_p]
        self.lib.memoria_mobile_flush.restype = ctypes.c_int
        self.lib.memoria_mobile_free_buffer.argtypes = [Buffer]
        for name in (
            "observe_structural_text", "probe_structural_regions",
            "probe_structural_trails", "read_structural_window",
        ):
            fn = getattr(self.lib, f"memoria_mobile_{name}_json")
            fn.argtypes = [ctypes.c_void_p, Buffer, ctypes.POINTER(Buffer)]
            fn.restype = ctypes.c_int
        self.data_dir = data_dir
        self.handle = ctypes.c_void_p()
        self.open()

    def open(self) -> None:
        status = self.lib.memoria_mobile_open(
            str(self.data_dir).encode(), b"private-region-replay",
            ctypes.byref(self.handle),
        )
        if status != 0:
            raise RuntimeError("native open failed")

    def reopen(self) -> None:
        if self.lib.memoria_mobile_flush(self.handle) != 0:
            raise RuntimeError("native flush failed")
        self.close()
        self.open()

    def close(self) -> None:
        if self.handle.value:
            self.lib.memoria_mobile_close(self.handle)
            self.handle = ctypes.c_void_p()

    def call(self, name: str, request: dict) -> tuple[int, dict]:
        encoded = json.dumps(request, ensure_ascii=False, separators=(",", ":")).encode()
        raw = (ctypes.c_uint8 * len(encoded)).from_buffer_copy(encoded)
        response = Buffer()
        status = getattr(self.lib, f"memoria_mobile_{name}_json")(
            self.handle, Buffer(raw, len(encoded)), ctypes.byref(response)
        )
        try:
            value = json.loads(ctypes.string_at(response.data, response.size))
        finally:
            if response.data:
                self.lib.memoria_mobile_free_buffer(response)
        return status, value

    def witness_exists(self, hierarchy_id: str, witness: dict) -> bool:
        offset = 0
        token = None
        while True:
            request = {"hierarchy_id": hierarchy_id, "offset": offset, "limit": 64}
            if token is not None:
                request["expected_token"] = token
            status, window = self.call("read_structural_window", request)
            if status != 0:
                raise RuntimeError("addressable window read failed")
            token = window["window_token"]
            if any(
                row["source_id"] == witness["source_id"]
                and row["sequence"] == witness["sequence"]
                and row["source_kind"] == witness["source_kind"]
                for row in window["observations"]
            ):
                return True
            offset = window["page"]["next_offset"]
            if offset is None:
                return False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export", type=Path, required=True)
    parser.add_argument("--queries", type=Path, required=True,
                        help="Private JSON array of query strings; never printed")
    parser.add_argument("--library", type=Path, required=True,
                        help="Built libmemoria_mobile shared library")
    args = parser.parse_args()
    export = json.loads(args.export.read_text(encoding="utf-8"))
    observations = export["structural"]["observations"]
    queries = json.loads(args.queries.read_text(encoding="utf-8"))
    if not isinstance(queries, list) or not queries or not all(
        isinstance(query, str) and query for query in queries
    ):
        raise ValueError("queries must be a nonempty JSON array of strings")

    with tempfile.TemporaryDirectory(prefix="memoria-region-replay-") as directory:
        probe = NativeProbe(args.library, Path(directory))
        try:
            field_updates = 0
            duplicate_sources = 0
            for observation in observations:
                status, recorded = probe.call("observe_structural_text", observation)
                if status != 0:
                    raise RuntimeError("native observation failed")
                field_updates += bool(recorded["new_trail"])
                duplicate_sources += bool(recorded["duplicate"])
            probe.reopen()
            results = []
            for index, query in enumerate(queries):
                region_status, region = probe.call(
                    "probe_structural_regions", {"query": query, "limit": 16}
                )
                offset = 0
                groups = []
                trails = None
                while True:
                    trail_status, page = probe.call(
                        "probe_structural_trails",
                        {"query": query, "offset": offset, "limit": 64},
                    )
                    if trail_status != 2 or page["qualified"]:
                        raise RuntimeError("unqualified trail contract violated")
                    if trails is None:
                        trails = page
                    groups.extend(page["groups"])
                    offset = page["page"]["next_offset"]
                    if offset is None:
                        break
                if region_status != 2 or region["qualified"]:
                    raise RuntimeError("unqualified probe contract violated")
                if len(groups) != trails["group_count"]:
                    raise RuntimeError("trail pagination gate failed")
                bases = {group["fingerprint"] for group in groups
                         if group["query_echo"]}
                composed = [group for group in groups
                            if group["composition"] is not None]
                if any(
                    not group["contains_query_trail"]
                    or group["composition"]["base_address"] not in bases
                    or group["composition"]["positions"] < 1
                    for group in composed
                ) or len(composed) != (
                    trails["embedded_payload_count"] if bases else 0
                ):
                    raise RuntimeError("observed base composition gate failed")
                witnesses = [r for r in region["regions"] if r["witness"] is not None]
                missing = sum(
                    not probe.witness_exists(r["hierarchy_id"], r["witness"])
                    for r in witnesses
                )
                results.append({
                    "case": index,
                    "activated_regions": region["region_count"],
                    "unseen_query_symbols": region["unseen_query_symbols"],
                    "ordered_span_top16": dict(sorted(Counter(
                        r["max_ordered_span"] for r in region["regions"]
                    ).items())),
                    "query_echo_occurrences": trails["query_echo_occurrences"],
                    "embedded_payloads": trails["embedded_payload_count"],
                    "embedded_occurrences": trails["embedded_occurrences"],
                    "composed_payloads": len(composed),
                    "composed_with_prefix": sum(
                        group["composition"]["prefix_symbols"] > 0
                        for group in composed
                    ),
                    "composed_with_suffix": sum(
                        group["composition"]["suffix_symbols"] > 0
                        for group in composed
                    ),
                    "witnesses_checked": len(witnesses),
                    "witnesses_missing": missing,
                    "qualified": region["qualified"],
                })
                if missing:
                    raise RuntimeError("witness addressability gate failed")
        finally:
            probe.close()
    print(json.dumps({
        "observations": len(observations),
        "regions": len({row["hierarchy_id"] for row in observations}),
        "distinct_region_trails": field_updates,
        "duplicate_source_events": duplicate_sources,
        "cases": results,
    }, sort_keys=True))


if __name__ == "__main__":
    main()
