from memoria_resolutiva.polysemy_stability import evaluate_polysemy_order_stability


def main():
    finance = [
        "banco aprovou credito cliente",
        "banco concedeu emprestimo cliente",
        "cliente abriu conta banco",
        "banco cobrou juros financiamento",
        "banco recebeu deposito cliente",
    ]
    data = [
        "banco armazenou dados sistema",
        "banco recebeu registros aplicacao",
        "consulta acessou banco dados",
        "servidor gravou informacao banco",
        "banco possui tabelas registros",
    ]

    summary = evaluate_polysemy_order_stability(finance, data, shuffled_runs=50, seed=12345)
    print("separation_rate:", summary.separation_rate)
    print("median_sense_count:", summary.median_sense_count)
    for run in summary.runs[:10]:
        print(run)


if __name__ == "__main__":
    main()
