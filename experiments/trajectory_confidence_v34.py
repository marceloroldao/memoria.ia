from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.trajectory_confidence import AutoConceptConfidence, derive_trajectory_evidence


def main():
    m = PolysemyMemory(window=3, split_threshold=0.18)
    for sentence in [
        "banco aprovou credito cliente",
        "banco concedeu emprestimo cliente",
        "cliente abriu conta banco",
        "banco cobrou juros financiamento",
        "banco recebeu deposito cliente",
        "banco armazenou dados sistema",
        "banco recebeu registros aplicacao",
        "consulta acessou banco dados",
        "servidor gravou informacao banco",
        "banco possui tabelas registros",
    ]:
        m.observe(sentence)

    senses = m.senses("banco")
    print("sense_count", len(senses))
    if len(senses) < 2:
        return

    confidence = AutoConceptConfidence()
    for i in range(len(senses) - 1):
        evidence = derive_trajectory_evidence(senses[i], senses[i + 1])
        p = confidence.update(evidence)
        print(i, evidence, "merge_probability", round(p, 4), "state", confidence.state)


if __name__ == "__main__":
    main()
