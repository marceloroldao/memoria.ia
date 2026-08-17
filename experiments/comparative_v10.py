from statistics import mean

from memoria_resolutiva.textual import TextContextMemory
from memoria_resolutiva.word2vec_baseline import Word2VecBaseline

PAIRS = [("carro", "automovel"), ("guardar", "armazenar"), ("fibra", "enlace"), ("estrela", "astro")]
DISTRACTORS = {"veiculo", "salvar", "cabo", "planeta"}
CANDIDATES = set(sum(([a, b] for a, b in PAIRS), [])) | DISTRACTORS
TRAIN = [
    "o carro percorreu a estrada rapidamente", "o automovel percorreu a estrada rapidamente",
    "a estrada recebeu o carro durante a viagem", "a estrada recebeu o automovel durante a viagem",
    "guardar os dados no sistema evita perdas", "armazenar os dados no sistema evita perdas",
    "o sistema permite guardar registros com segurança", "o sistema permite armazenar registros com segurança",
    "a fibra transporta sinal entre os equipamentos", "o enlace transporta sinal entre os equipamentos",
    "os equipamentos recebem sinal pela fibra principal", "os equipamentos recebem sinal pelo enlace principal",
    "a estrela aparece brilhante no céu noturno", "o astro aparece brilhante no céu noturno",
    "o céu noturno mostra a estrela distante", "o céu noturno mostra o astro distante",
    "a estrada percorreu o veiculo rapidamente carro", "o cabo recebe sinal dos equipamentos fibra",
    "salvar no sistema dados pode guardar registros", "o planeta no céu aparece próximo da estrela",
]


def evaluate(similarity):
    expected = {a: b for a, b in PAIRS} | {b: a for a, b in PAIRS}
    top1, margins = 0, []
    for query, target in expected.items():
        ranked = sorted(((c, similarity(query, c)) for c in CANDIDATES if c != query), key=lambda x: x[1], reverse=True)
        top1 += int(ranked and ranked[0][0] == target)
        target_score = similarity(query, target)
        distractor = max(similarity(query, d) for d in DISTRACTORS if d != query)
        margins.append(target_score - distractor)
    return top1, mean(margins), min(margins)


if __name__ == "__main__":
    resolutive = TextContextMemory(radius=3)
    resolutive.observe_many(TRAIN)
    print("resolutive", evaluate(resolutive.associator.similarity))

    for seed in range(1, 6):
        w2v = Word2VecBaseline(vector_size=32, window=3, seed=seed, epochs=300)
        w2v.fit(TRAIN)
        print(f"word2vec seed={seed}", evaluate(w2v.similarity))
