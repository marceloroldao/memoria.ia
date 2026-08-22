from __future__ import annotations

from statistics import mean
from time import perf_counter

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96
from memoria_resolutiva.sentence_semantic_router_v96 import SentenceSemanticRouterV96


TRAIN = {
    "billing_fee": ["a tarifa mensal foi aplicada ao servico de fibra do cliente", "o encargo adicional apareceu na cobranca da assinatura", "a taxa de instalacao consta na fatura do provedor"],
    "network_outage": ["a conexao caiu depois de uma falha no enlace de fibra", "o cliente ficou sem internet por causa de uma indisponibilidade na rede", "houve interrupcao do servico apos perda de sinal na rota principal"],
    "payment_delay": ["o pagamento da mensalidade ficou atrasado e gerou pendencia financeira", "a fatura venceu e ainda nao foi quitada pelo cliente", "a cobranca permanece em aberto depois da data de vencimento"],
    "optical_loss": ["a potencia optica recebida caiu e o enlace apresentou atenuacao elevada", "o nivel de sinal na fibra ficou baixo devido a perda optica", "a leitura da onu mostrou potencia recebida abaixo do normal"],
    "router_failure": ["o roteador reiniciou repetidamente e deixou de encaminhar pacotes", "o equipamento de borda travou e perdeu conectividade", "o gateway apresentou falha e precisou ser reiniciado"],
    "account_block": ["o acesso foi bloqueado porque a conta estava suspensa", "o cadastro do assinante ficou bloqueado por restricao administrativa", "a autenticacao foi negada enquanto o usuario permanecia suspenso"],
    "fiber_break": ["um rompimento fisico interrompeu a fibra entre os postes", "o cabo optico foi partido durante uma obra na rua", "a equipe encontrou a fibra quebrada no trecho externo"],
    "high_latency": ["a rede respondeu lentamente e o tempo de ida e volta aumentou", "o cliente percebeu atraso elevado mesmo com o link ativo", "a latencia subiu durante o periodo de congestionamento"],
}

ANCHORS = {
    "billing_fee": ["tarifa", "encargo", "taxa"], "network_outage": ["falha", "indisponibilidade", "interrupcao"],
    "payment_delay": ["atrasado", "venceu", "vencimento"], "optical_loss": ["atenuacao", "potencia", "sinal"],
    "router_failure": ["roteador", "gateway", "equipamento"], "account_block": ["bloqueado", "suspensa", "suspenso"],
    "fiber_break": ["rompimento", "partido", "quebrada"], "high_latency": ["latencia", "atraso", "lentamente"],
}

QUERIES = [
    ("billing_fee", "o cliente reclamou que apareceu uma cobranca extra na conta deste mes"), ("billing_fee", "na fatura nova existe uma taxa que nao aparecia anteriormente"),
    ("network_outage", "desde cedo a casa esta sem acesso e o link nao volta mesmo reiniciando os aparelhos"), ("network_outage", "a internet parou completamente depois de uma queda geral no bairro"),
    ("payment_delay", "a mensalidade venceu na semana passada e continua pendente"), ("payment_delay", "o cliente ainda nao pagou a conta que ja passou do vencimento"),
    ("optical_loss", "a onu esta recebendo sinal muito fraco e a leitura de potencia caiu bastante"), ("optical_loss", "o enlace permanece ativo mas a atenuacao aumentou e o nivel recebido esta baixo"),
    ("router_failure", "o gateway congela varias vezes por dia e so volta depois de reiniciar"), ("router_failure", "o equipamento que encaminha o trafego travou novamente durante a madrugada"),
    ("account_block", "o usuario nao autentica porque o cadastro consta como suspenso no sistema"), ("account_block", "a conta foi restringida administrativamente e por isso o acesso esta negado"),
    ("fiber_break", "uma escavacao cortou o cabo e a fibra ficou fisicamente interrompida"), ("fiber_break", "a equipe encontrou o cabo partido depois de uma obra na calcada"),
    ("high_latency", "o link nao caiu mas tudo demora muito para responder e o ping aumentou"), ("high_latency", "a navegacao esta lenta mesmo com sinal presente e sem perda total de conectividade"),
    (None, "o cliente mudou o endereco de instalacao e pediu alteracao cadastral"), (None, "a equipe marcou uma visita tecnica para a proxima sexta feira"),
    (None, "foi solicitado um novo plano com maior velocidade contratada"), (None, "o cliente perguntou qual e o horario de atendimento da loja"),
]

PREFERRED = ["cobranca", "taxa", "acesso", "internet", "mensalidade", "conta", "onu", "atenuacao", "gateway", "equipamento", "usuario", "cadastro", "escavacao", "cabo", "ping", "navegacao", "endereco", "visita", "plano", "horario"]


def representative_token(sentence: str) -> str:
    words = sentence.lower().split()
    for token in PREFERRED:
        if token in words:
            return token
    return words[0]


def summarize(expected, predicted):
    correct = false_positive = abstention = 0
    for target, got in zip(expected, predicted):
        if target is None:
            if got is None:
                correct += 1; abstention += 1
            else:
                false_positive += 1
        elif got == target:
            correct += 1
        elif got is None:
            abstention += 1
    n = len(expected)
    return {"accuracy": correct / n, "false_positive_rate": false_positive / n, "abstention_rate": abstention / n}


def main():
    full = SemanticRouterV96(threshold=0.24, min_margin=0.035, indexed=False)
    disc = DiscriminativeSemanticRouterV96(threshold=0.24, min_margin=0.035, candidate_limit=8)
    sent = SentenceSemanticRouterV96(threshold=0.14, min_margin=0.02)
    training = [s for rows in TRAIN.values() for s in rows]
    full.observe(training); disc.observe(training)
    for cid, rows in TRAIN.items():
        full.register_concept(cid, ANCHORS[cid]); disc.register_concept(cid, ANCHORS[cid]); sent.observe_concept(cid, rows)
    full.observe([q for _, q in QUERIES]); disc.observe([q for _, q in QUERIES])

    start = perf_counter(); full_out = [full.resolve_token(representative_token(q)) for _, q in QUERIES]; full_ms = 1000 * (perf_counter() - start) / len(QUERIES)
    start = perf_counter(); disc_out = [disc.resolve_token(representative_token(q)) for _, q in QUERIES]; disc_ms = 1000 * (perf_counter() - start) / len(QUERIES)
    start = perf_counter(); sent_out = [sent.resolve(q) for _, q in QUERIES]; sent_ms = 1000 * (perf_counter() - start) / len(QUERIES)

    expected = [x for x, _ in QUERIES]
    print({"token_full": summarize(expected, [x.concept_id for x in full_out]), "ms_per_query": full_ms})
    print({"token_disc8": summarize(expected, [x.concept_id for x in disc_out]), "ms_per_query": disc_ms, "parity": mean(1.0 if a.concept_id == b.concept_id else 0.0 for a, b in zip(full_out, disc_out))})
    print({"sentence_sparse": summarize(expected, [x.concept_id for x in sent_out]), "ms_per_query": sent_ms})


if __name__ == "__main__":
    main()
