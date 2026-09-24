from __future__ import annotations

import argparse
import json
from pathlib import Path

from memoria_resolutiva.evolving_address_state_v2 import EvolvingAddressStateJournalV2
from memoria_resolutiva.progressive_llm_benchmark_v2 import (
    measure_structural_pre_language_v2,
    measure_temporal_pre_language_v2,
    summarize_r14_measurements_v2,
)
from memoria_resolutiva.resolutive_inference_v2 import ResolutiveInferenceEngineV2
from memoria_resolutiva.structural_trajectory_v2 import StructuralTrajectoryIndex

from product_context_benchmark import run_benchmark as run_product_control


def _engine():
    index = StructuralTrajectoryIndex()
    rows = [
        ("dominant:a", [10, 20, 30]),
        ("dominant:b", [10, 20, 30]),
        ("dominant:c", [10, 20, 30]),
        ("competing", [10, 20, 40]),
        ("ambiguous:a", [5, 6, 7]),
        ("ambiguous:b", [5, 6, 8]),
    ]
    for sequence, (source, addresses) in enumerate(rows):
        index.ingest_addresses(
            addresses,
            hierarchy_id="r14",
            source_id=source,
            sequence=sequence,
            observation_id=f"obs:{source}",
        )
    journal = EvolvingAddressStateJournalV2()
    journal.append(77, hierarchy_id="r14", sequence=1, payload_addresses=[700])
    journal.append(77, hierarchy_id="r14", sequence=2, payload_addresses=[800])
    return ResolutiveInferenceEngineV2(index, state_reader=journal)


def run():
    engine = _engine()
    structural = (
        measure_structural_pre_language_v2(
            engine, [10, 20], hierarchy_id="r14", case_id="resolved",
            expected_status="resolved", expected_resolved_address=30,
        ),
        measure_structural_pre_language_v2(
            engine, [5, 6], hierarchy_id="r14", case_id="ambiguous",
            expected_status="ambiguous",
        ),
        measure_structural_pre_language_v2(
            engine, [999, 1000], hierarchy_id="r14", case_id="negative",
            expected_status="unresolved",
        ),
    )
    temporal = (
        measure_temporal_pre_language_v2(
            engine, 77, hierarchy_id="r14", case_id="current",
            operation="current", expected_payload_addresses=(800,),
        ),
        measure_temporal_pre_language_v2(
            engine, 77, hierarchy_id="r14", case_id="change",
            operation="change", expected_payload_addresses=(800,),
        ),
    )
    result = summarize_r14_measurements_v2(structural=structural, temporal=temporal)
    result["product_context_control"] = run_product_control()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run()
    rendered = json.dumps(result, indent=2, ensure_ascii=False, sort_keys=True)
    print(rendered)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
