from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.concept_revision import ConceptRevisionHistory, snapshot_from_memory


def main():
    memory = PolysemyMemory(window=3, split_threshold=0.18)
    history = ConceptRevisionHistory()

    early = [
        "banco recebeu cliente dados",
        "banco registrou conta sistema",
        "banco processou registro cliente",
    ]
    for sentence in early:
        memory.observe(sentence)
    s1 = snapshot_from_memory(history, memory, "banco", epoch=1, threshold=0.18)

    later_finance = [
        "banco aprovou credito cliente",
        "banco concedeu emprestimo cliente",
        "cliente abriu conta banco",
    ]
    later_data = [
        "banco armazenou dados sistema",
        "consulta acessou banco dados",
        "banco possui tabelas registros",
    ]
    for sentence in later_finance + later_data:
        memory.observe(sentence)
    s2 = snapshot_from_memory(history, memory, "banco", epoch=2, threshold=0.30)

    print("epoch1", s1.groups)
    print("epoch2", s2.groups)
    print("revisions", [(a.epoch, b.epoch) for a, b in history.revisions("banco")])
    print("historical_epoch1", history.at("banco", 1).groups)
    print("current", history.current("banco").groups)


if __name__ == "__main__":
    main()
