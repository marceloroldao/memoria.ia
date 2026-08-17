from memoria_resolutiva.end_to_end import EndToEndOnlineBenchmark


def _batch(a: str, b: str, context: str):
    return [
        f"{a} aparece no mesmo contexto operacional que {context}",
        f"{b} aparece no mesmo contexto operacional que {context}",
        f"sistema relaciona {a} com {context} durante uso",
        f"sistema relaciona {b} com {context} durante uso",
    ] * 8


def test_online_benchmark_incorporates_without_replaying_resolutive_history():
    bench = EndToEndOnlineBenchmark(radius=3)
    first = bench.observe_batch(_batch("carro", "automovel", "cidade"), ("carro", "automovel"))
    second = bench.observe_batch(_batch("fibra", "enlace", "rede"), ("fibra", "enlace"))

    assert first.resolutive_immediate_top1 == 1.0
    assert second.resolutive_immediate_top1 == 1.0
    assert second.resolutive_retention_top1 == 1.0
    assert second.cooccurrence_retention_top1 == 1.0
    assert second.tfidf_retention_top1 == 1.0
    assert second.observations == 64


def test_end_to_end_reports_structural_growth_without_speed_assumptions():
    bench = EndToEndOnlineBenchmark(radius=3)
    first = bench.observe_batch(_batch("carro", "automovel", "cidade"), ("carro", "automovel"))
    second = bench.observe_batch(_batch("fibra", "enlace", "rede"), ("fibra", "enlace"))

    assert second.resolutive_nodes >= first.resolutive_nodes
    assert second.resolutive_features >= first.resolutive_features
    assert second.cooccurrence_nodes >= first.cooccurrence_nodes
    assert second.cooccurrence_features >= first.cooccurrence_features
    assert first.resolutive_update_seconds >= 0.0
    assert first.tfidf_rebuild_seconds >= 0.0
