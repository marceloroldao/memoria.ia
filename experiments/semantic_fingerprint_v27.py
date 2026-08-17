from memoria_resolutiva.dependency_inference import lexical_jaccard
from memoria_resolutiva.semantic_fingerprint import hybrid_similarity


ORIGIN = "Nova cobrança mensal de 12 reais será aplicada às conexões de fibra óptica dos provedores"
COPIES = [
    "Provedores terão de pagar taxa mensal de R$ 12 por enlaces de fibra.",
    "Uma tarifa de 12 reais por mês passará a incidir sobre conexões ópticas das operadoras.",
    "Serviços de fibra das empresas terão custo extra mensal de 12 reais.",
    "Foi criado encargo de doze reais mensais para os links ópticos usados por provedores.",
    "As operadoras pagarão 12 reais a mais todo mês pelo uso de fibra.",
]
INDEPENDENT = [
    "Provedores ampliaram redes de fibra em 12 cidades neste mês.",
    "Operadoras reduziram em 12 por cento o preço de planos de internet.",
    "O telescópio registrou uma estrela a 12 anos-luz.",
]


def metrics(scores, labels, threshold):
    tp = fp = fn = 0
    for score, label in zip(scores, labels):
        pred = score >= threshold
        tp += int(pred and label)
        fp += int(pred and not label)
        fn += int((not pred) and label)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return precision, recall, tp, fp, fn


def main():
    docs = COPIES + INDEPENDENT
    labels = [True] * len(COPIES) + [False] * len(INDEPENDENT)

    lexical = [lexical_jaccard(ORIGIN, text) for text in docs]
    hybrid = [hybrid_similarity(ORIGIN, text) for text in docs]

    lp, lr, *_ = metrics(lexical, labels, threshold=0.20)
    hp, hr, *_ = metrics(hybrid, labels, threshold=0.40)

    print(f"lexical precision={lp:.3f} recall={lr:.3f}")
    print(f"hybrid  precision={hp:.3f} recall={hr:.3f}")
    for label, text, lscore, hscore in zip(labels, docs, lexical, hybrid):
        print("copy" if label else "independent", f"lex={lscore:.3f}", f"hybrid={hscore:.3f}", text)


if __name__ == "__main__":
    main()
