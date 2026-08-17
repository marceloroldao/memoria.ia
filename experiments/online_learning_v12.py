from memoria_resolutiva.online_learning import OnlineLearningEvaluator

BATCHES = [
    (("carro", "automovel"), [
        "carro percorre estrada urbana rapidamente",
        "automovel percorre estrada urbana rapidamente",
        "motorista conduz carro pela estrada",
        "motorista conduz automovel pela estrada",
        "viagem usa carro na cidade",
        "viagem usa automovel na cidade",
    ] * 20),
    (("fibra", "enlace"), [
        "fibra transporta sinal entre equipamentos",
        "enlace transporta sinal entre equipamentos",
        "rede monitora fibra durante transmissao",
        "rede monitora enlace durante transmissao",
        "equipamentos recebem sinal por fibra",
        "equipamentos recebem sinal por enlace",
    ] * 20),
    (("guardar", "armazenar"), [
        "sistema permite guardar dados com seguranca",
        "sistema permite armazenar dados com seguranca",
        "operador decide guardar registros importantes",
        "operador decide armazenar registros importantes",
        "rotina usa guardar informacoes persistentes",
        "rotina usa armazenar informacoes persistentes",
    ] * 20),
    (("estrela", "astro"), [
        "estrela aparece brilhante no ceu",
        "astro aparece brilhante no ceu",
        "telescopio observa estrela distante",
        "telescopio observa astro distante",
        "ceu noturno mostra estrela luminosa",
        "ceu noturno mostra astro luminoso",
    ] * 20),
]


def main() -> None:
    evaluator = OnlineLearningEvaluator(radius=3)
    for pair, batch in BATCHES:
        step = evaluator.observe_batch(batch, pair)
        print(
            f"step={step.step} observations={step.observations} "
            f"update_ms={step.update_seconds * 1000:.3f} "
            f"immediate_top1={step.immediate_top1:.3f} "
            f"retention_top1={step.retention_top1:.3f}"
        )


if __name__ == "__main__":
    main()
