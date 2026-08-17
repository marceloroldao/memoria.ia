from memoria_resolutiva.adversarial_dependency import evaluate_dependency_edges
from memoria_resolutiva.dependency_inference import SourceDocument


def build_documents():
    docs = [
        SourceDocument("origem_falsa", 1, "governo confirmou novo imposto especial sobre fibra optica", cites=()),
        SourceDocument("copia_1", 2, "novo imposto especial sobre fibra optica foi confirmado pelo governo", cites=()),
        SourceDocument("copia_2", 4, "autoridades anunciaram tributacao adicional incidente sobre servicos de fibra", cites=()),
        SourceDocument("copia_3", 8, "servicos de internet por fibra passarao a pagar nova taxa governamental", cites=()),
        SourceDocument("verdadeira_1", 3, "diario oficial nao publicou qualquer novo imposto sobre servicos de fibra", cites=()),
        SourceDocument("verdadeira_2", 6, "legislacao vigente permanece sem nova tributacao especifica para fibra optica", cites=()),
        SourceDocument("verdadeira_3", 10, "consulta independente ao diario oficial nao encontrou criacao da taxa mencionada", cites=()),
    ]
    truth = {
        "origem_falsa": None,
        "copia_1": "origem_falsa",
        "copia_2": "origem_falsa",
        "copia_3": "origem_falsa",
        "verdadeira_1": None,
        "verdadeira_2": None,
        "verdadeira_3": None,
    }
    return docs, truth


def main():
    docs, truth = build_documents()
    for threshold in (0.55, 0.65, 0.72, 0.80):
        report = evaluate_dependency_edges(docs, truth, threshold=threshold)
        print(threshold, report)


if __name__ == "__main__":
    main()
