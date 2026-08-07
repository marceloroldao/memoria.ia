from memoria_resolutiva.end_to_end import EndToEndOnlineBenchmark


PAIRS = [
    ("carro", "automovel", "cidade"),
    ("fibra", "enlace", "rede"),
    ("guardar", "armazenar", "dados"),
    ("estrela", "astro", "ceu"),
    ("rapido", "veloz", "processo"),
    ("casa", "residencia", "bairro"),
    ("erro", "falha", "sistema"),
    ("medico", "doutor", "clinica"),
    ("aluno", "estudante", "escola"),
    ("compra", "aquisicao", "mercado"),
]


def batch(a: str, b: str, context: str, repeat: int = 25) -> list[str]:
    sentences = [
        f"{a} aparece no mesmo contexto operacional que {context}",
        f"{b} aparece no mesmo contexto operacional que {context}",
        f"sistema relaciona {a} com {context} durante uso",
        f"sistema relaciona {b} com {context} durante uso",
    ]
    return sentences * repeat


def main() -> None:
    benchmark = EndToEndOnlineBenchmark(radius=3)
    for a, b, context in PAIRS:
        step = benchmark.observe_batch(batch(a, b, context), (a, b))
        print(
            f"step={step.step:02d} obs={step.observations:04d} "
            f"update_ms(res={step.resolutive_update_seconds*1000:.3f}, "
            f"cooc={step.cooccurrence_update_seconds*1000:.3f}, "
            f"tfidf_rebuild={step.tfidf_rebuild_seconds*1000:.3f}) "
            f"immediate={step.resolutive_immediate_top1:.3f} "
            f"retention(res={step.resolutive_retention_top1:.3f}, "
            f"cooc={step.cooccurrence_retention_top1:.3f}, "
            f"tfidf={step.tfidf_retention_top1:.3f}) "
            f"footprint(res_nodes={step.resolutive_nodes}, res_features={step.resolutive_features}, "
            f"cooc_nodes={step.cooccurrence_nodes}, cooc_features={step.cooccurrence_features})"
        )


if __name__ == "__main__":
    main()
