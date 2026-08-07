from memoria_resolutiva.baselines import WindowCooccurrenceBaseline
from memoria_resolutiva.textual import TextContextMemory

PAIRS = [
    ("carro", "automovel"),
    ("guardar", "armazenar"),
    ("fibra", "enlace"),
    ("estrela", "astro"),
]

SENTENCES = [
    "o carro atravessou a estrada durante a chuva",
    "o automovel atravessou a estrada durante a chuva",
    "pela manhã o carro ficou estacionado perto da oficina",
    "pela manhã o automovel ficou estacionado perto da oficina",
    "um carro novo consumiu menos combustível na viagem",
    "um automovel novo consumiu menos combustível na viagem",
    "o sistema precisa guardar os dados antes da reinicialização",
    "o sistema precisa armazenar os dados antes da reinicialização",
    "vamos guardar os registros em local seguro",
    "vamos armazenar os registros em local seguro",
    "é necessário guardar informação para consulta futura",
    "é necessário armazenar informação para consulta futura",
    "a fibra apresentou perda elevada durante a medição",
    "o enlace apresentou perda elevada durante a medição",
    "técnicos analisaram a fibra depois da falha óptica",
    "técnicos analisaram o enlace depois da falha óptica",
    "a fibra permaneceu estável durante o teste de potência",
    "o enlace permaneceu estável durante o teste de potência",
    "a estrela apareceu brilhante no céu noturno",
    "o astro apareceu brilhante no céu noturno",
    "cientistas observaram a estrela com o telescópio",
    "cientistas observaram o astro com o telescópio",
    "a estrela distante apresentou variação de luminosidade",
    "o astro distante apresentou variação de luminosidade",
] + [
    "o cabo apresentou perda elevada durante a medição",
    "o planeta apareceu brilhante no céu noturno",
    "o veículo atravessou a estrada durante a chuva",
    "o programa deve salvar os dados antes da reinicialização",
    "o banco aprovou crédito para o cliente",
    "o banco de dados armazenou registros importantes",
] * 5

CANDIDATES = [
    "carro", "automovel", "guardar", "armazenar", "fibra", "enlace",
    "estrela", "astro", "cabo", "planeta", "veículo", "salvar",
]


def evaluate(name, similarity):
    total = 0
    top1 = 0
    margins = []
    for a, b in PAIRS:
        for query, target in ((a, b), (b, a)):
            ranked = sorted(
                ((candidate, similarity(query, candidate)) for candidate in CANDIDATES if candidate != query),
                key=lambda item: item[1],
                reverse=True,
            )
            total += 1
            if ranked and ranked[0][0] == target:
                top1 += 1
            target_score = next(score for node, score in ranked if node == target)
            best_other = max(score for node, score in ranked if node != target)
            margins.append(target_score - best_other)
    print(name)
    print(f"  top1={top1}/{total} ({top1/total:.3f})")
    print(f"  mean_margin={sum(margins)/len(margins):.4f}")
    print(f"  min_margin={min(margins):.4f}")


resolutive = TextContextMemory(radius=3)
resolutive.observe_many(SENTENCES)

baseline = WindowCooccurrenceBaseline(radius=3)
baseline.observe_many(SENTENCES)

evaluate("resolutive_signed_context", resolutive.associator.similarity)
evaluate("unordered_window_cooccurrence", baseline.similarity)
