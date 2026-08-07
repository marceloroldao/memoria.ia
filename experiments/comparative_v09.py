from memoria_resolutiva.textual import TextContextMemory
from memoria_resolutiva.tfidf_context import TfidfContextBaseline

PAIRS = [
    ("carro", "automovel"),
    ("guardar", "armazenar"),
    ("fibra", "enlace"),
    ("estrela", "astro"),
]
DISTRACTORS = {"veiculo", "salvar", "cabo", "planeta"}
CANDIDATES = set(sum(([a, b] for a, b in PAIRS), [])) | DISTRACTORS

TRAIN = [
    "o carro percorreu a estrada rapidamente",
    "o automovel percorreu a estrada rapidamente",
    "a estrada recebeu o carro durante a viagem",
    "a estrada recebeu o automovel durante a viagem",
    "guardar os dados no sistema evita perdas",
    "armazenar os dados no sistema evita perdas",
    "o sistema permite guardar registros com segurança",
    "o sistema permite armazenar registros com segurança",
    "a fibra transporta sinal entre os equipamentos",
    "o enlace transporta sinal entre os equipamentos",
    "os equipamentos recebem sinal pela fibra principal",
    "os equipamentos recebem sinal pelo enlace principal",
    "a estrela aparece brilhante no céu noturno",
    "o astro aparece brilhante no céu noturno",
    "o céu noturno mostra a estrela distante",
    "o céu noturno mostra o astro distante",
    "a estrada percorreu o veiculo rapidamente carro",
    "o cabo recebe sinal dos equipamentos fibra",
    "salvar no sistema dados pode guardar registros",
    "o planeta no céu aparece próximo da estrela",
]


def evaluate(name, similarity):
    expected = {a: b for a, b in PAIRS} | {b: a for a, b in PAIRS}
    top1 = 0
    margins = []
    for query, target in expected.items():
        ranked = sorted(
            ((c, similarity(query, c)) for c in CANDIDATES if c != query),
            key=lambda item: item[1],
            reverse=True,
        )
        correct = ranked[0][0] == target
        top1 += int(correct)
        target_score = similarity(query, target)
        distractor_score = max(similarity(query, d) for d in DISTRACTORS if d != query)
        margins.append(target_score - distractor_score)
        print(f"{name:12s} {query:12s} -> {ranked[0][0]:12s} score={ranked[0][1]:.3f} margin={margins[-1]:.3f}")
    print(f"{name}: top1={top1}/{len(expected)} mean_margin={sum(margins)/len(margins):.3f} min_margin={min(margins):.3f}")


if __name__ == "__main__":
    resolutive = TextContextMemory(radius=3)
    tfidf = TfidfContextBaseline(radius=3)
    resolutive.observe_many(TRAIN)
    tfidf.observe_many(TRAIN)

    evaluate("resolutive", resolutive.associator.similarity)
    evaluate("tfidf", tfidf.similarity)
