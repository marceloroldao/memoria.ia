"""Compare native query latency over the same reopened BDR on two builds.

Run with PYTHONPATH=src python benchmarks/benchmark_native_temporal_recall.py
--baseline /path/to/baseline.so --candidate /path/to/candidate.so.
"""
from argparse import ArgumentParser
from contextlib import closing
from pathlib import Path
from statistics import median
from tempfile import TemporaryDirectory
from time import perf_counter_ns

from memoria_resolutiva.native_conversation import NativeConversationService


SESSION = "temporal-benchmark"
OBSERVATIONS = (
    (10, "A fonte Vega fornece 24 volts."),
    (15, "A fonte Vega é cinza."),
    (40, "A fonte Vega fornece 12 volts."),
    (45, "A fonte Vega é preta."),
    (60, "A fonte Vega fornece 24 volts."),
)
QUERIES = {
    "snapshot": "Qual era a tensão da fonte Vega na ordem 25?",
    "comparison": "O que mudou na fonte Vega entre as ordens 25 e 55?",
    "timeline": "Quais mudanças ocorreram na fonte Vega entre as ordens 25 e 70?",
}


def open_store(path: Path, library: Path):
    return closing(NativeConversationService(
        library_path=library, data_dir=path, organization_id="native-temporal-benchmark",
    ))


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--sizes", type=int, nargs="+", default=(128, 512, 2048))
    parser.add_argument("--samples", type=int, default=9)
    args = parser.parse_args()
    if args.samples < 1 or any(size < len(OBSERVATIONS) for size in args.sizes):
        parser.error("provide at least one sample and room for the target observations")

    print("records,query,baseline_median_ms,candidate_median_ms,speedup")
    for size in args.sizes:
        with TemporaryDirectory() as temp:
            path = Path(temp)
            with open_store(path, args.baseline) as store:
                for index in range(size - len(OBSERVATIONS)):
                    text = f"A fonte Auxiliar{index} fornece 5 volts."
                    store.ingest(role="user", text=text, order=index % 70 + 1, session_id=SESSION)
                for order, text in reversed(OBSERVATIONS):
                    store.ingest(role="user", text=text, order=order, session_id=SESSION)
                store.flush()

            # Alternate which build runs first across two rounds. Open and warm up
            # before timing so the comparison isolates recall on an open store.
            samples = [{route: [] for route in QUERIES} for _ in range(2)]
            expected = None
            for order in ((0, 1), (1, 0)):
                for index in order:
                    library = (args.baseline, args.candidate)[index]
                    with open_store(path, library) as store:
                        results = {route: store.resolve(query=query, session_id=SESSION)
                                   for route, query in QUERIES.items()}
                        if expected is None:
                            if any(result.status != "HIT" for result in results.values()):
                                raise RuntimeError("benchmark queries did not hit the reference store")
                            expected = results
                        elif results != expected:
                            raise RuntimeError("builds returned different temporal evidence")
                        for _ in range(args.samples):
                            for route, query in QUERIES.items():
                                start = perf_counter_ns()
                                store.resolve(query=query, session_id=SESSION)
                                samples[index][route].append(perf_counter_ns() - start)

        for route in QUERIES:
            baseline, candidate = (median(build[route]) / 1e6 for build in samples)
            print(f"{size},{route},{baseline:.3f},{candidate:.3f},{baseline / candidate:.2f}")


if __name__ == "__main__":
    main()
