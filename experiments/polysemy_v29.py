from memoria_resolutiva.polysemy import PolysemyMemory


def main():
    m = PolysemyMemory(window=3, split_threshold=0.18)

    finance = [
        "o banco aprovou credito para empresa",
        "o banco concedeu emprestimo ao cliente",
        "o cliente abriu conta no banco",
        "o banco cobrou juros do financiamento",
        "o banco recebeu deposito do cliente",
    ]
    data = [
        "o banco armazenou dados do sistema",
        "o banco recebeu registros da aplicacao",
        "a consulta acessou o banco de dados",
        "o servidor gravou informacao no banco",
        "o banco possui tabelas e registros",
    ]

    for sentence in finance + data:
        m.observe(sentence)

    print("senses banco:")
    for sense in m.describe("banco"):
        print(sense)

    print("finance query:", m.resolve("banco", {"credito", "cliente", "emprestimo", "conta"}))
    print("data query:", m.resolve("banco", {"dados", "registros", "servidor", "tabelas"}))


if __name__ == "__main__":
    main()
