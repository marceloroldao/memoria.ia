from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.sense_consolidation import consolidate_senses, resolve_group

FINANCE = [
    "banco aprovou credito cliente",
    "banco concedeu emprestimo cliente",
    "cliente abriu conta banco",
    "banco cobrou juros financiamento",
    "banco recebeu deposito cliente",
]
DATA = [
    "banco armazenou dados sistema",
    "banco recebeu registros aplicacao",
    "consulta acessou banco dados",
    "servidor gravou informacao banco",
    "banco possui tabelas registros",
]


def main():
    memory = PolysemyMemory(window=3, split_threshold=0.18)
    for sentence in FINANCE + DATA:
        memory.observe(sentence)

    micro = memory.describe("banco")
    groups = consolidate_senses(memory, "banco", threshold=0.24)
    print("micro_senses", len(micro))
    print("macro_groups", len(groups))
    for group in groups:
        print(group)

    finance = resolve_group(groups, {"credito", "cliente", "emprestimo", "conta", "juros"})
    data = resolve_group(groups, {"dados", "registros", "servidor", "tabelas", "consulta"})
    print("finance_group", finance)
    print("data_group", data)


if __name__ == "__main__":
    main()
