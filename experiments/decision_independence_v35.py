from memoria_resolutiva.decision_independence import DecisionIndependentConceptMemory


def main():
    m = DecisionIndependentConceptMemory()

    # Similar raw evidence first.
    for epoch, ctx in enumerate([
        {"credito", "cliente", "conta"},
        {"emprestimo", "cliente", "conta"},
        {"credito", "juros", "cliente"},
    ], start=1):
        m.observe(epoch, "tarifa", ctx)
        m.observe(epoch, "cobranca", ctx | {"mensal"})

    first = m.decide(3, "tarifa", "cobranca")
    repeat = m.decide(3, "tarifa", "cobranca")

    # New contradictory raw evidence arrives later.
    m.observe(4, "tarifa", {"tributo", "governo", "regulacao"})
    m.observe(4, "cobranca", {"fatura", "cliente", "pagamento"})
    m.observe(5, "tarifa", {"imposto", "setor", "regra"})
    m.observe(5, "cobranca", {"boleto", "servico", "pagamento"})
    later = m.decide(5, "tarifa", "cobranca")

    print("first", first)
    print("repeat_without_new_data", repeat)
    print("later_after_new_raw_evidence", later)
    print("history", m.decision_history("tarifa", "cobranca"))


if __name__ == "__main__":
    main()
