from memoria_resolutiva.polysemy_router_v96 import PolysemyRouterV96


def main():
    r = PolysemyRouterV96(threshold=0.25, min_margin=0.08)
    r.observe_sense("banco", "financial_bank", [
        "o banco aprovou o credito do cliente",
        "o banco recebeu o deposito na conta",
        "o banco cobrou juros do financiamento",
    ])
    r.observe_sense("banco", "seat_bench", [
        "o banco de madeira fica no parque",
        "sentamos no banco perto da arvore",
        "o banco da praca estava molhado pela chuva",
    ])

    cases = [
        ("banco", "o banco liberou credito para a conta do cliente", "financial_bank"),
        ("banco", "sentamos no banco de madeira perto do parque", "seat_bench"),
        ("banco", "eu vi o banco ontem", None),
    ]
    fallback_calls = []

    def fallback(surface, sentence):
        fallback_calls.append((surface, sentence))
        return "external"

    correct_direct = 0
    wrong_direct = 0
    for surface, sentence, expected in cases:
        direct = r.resolve(surface, sentence)
        if direct.concept_id is not None:
            if direct.concept_id == expected:
                correct_direct += 1
            else:
                wrong_direct += 1
        r.resolve_or_fallback(surface, sentence, fallback)
        print({
            "sentence": sentence,
            "expected": expected,
            "direct": direct.concept_id,
            "score": round(direct.score, 4),
            "margin": round(direct.margin, 4),
            "source": direct.source,
        })

    print({
        "metrics": r.metrics(),
        "correct_direct": correct_direct,
        "wrong_direct": wrong_direct,
        "fallback_calls": len(fallback_calls),
    })


if __name__ == "__main__":
    main()
