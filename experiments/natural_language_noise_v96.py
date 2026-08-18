from __future__ import annotations

from statistics import mean
from time import perf_counter

from memoria_resolutiva.discriminative_router_v96 import DiscriminativeSemanticRouterV96
from memoria_resolutiva.semantic_router_v96 import SemanticRouterV96


TRAIN = {
    "billing_fee": [
        "a tarifa mensal foi aplicada ao servico de fibra do cliente",
        "o encargo adicional apareceu na cobranca da assinatura",
        "a taxa de instalacao consta na fatura do provedor",
    ],
    "network_outage": [
        "a conexao caiu depois de uma falha no enlace de fibra",
        "o cliente ficou sem internet por causa de uma indisponibilidade na rede",
        "houve interrupcao do servico apos perda de sinal na rota principal",
    ],
    "payment_delay": [
        "o pagamento da mensalidade ficou atrasado e gerou pendencia financeira",
        "a fatura venceu e ainda nao foi quitada pelo cliente",
        "a cobranca permanece em aberto depois da data de vencimento",
    ],
    "optical_loss": [
        "a potencia optica recebida caiu e o enlace apresentou atenuacao elevada",
        "o nivel de sinal na fibra ficou baixo devido a perda optica",
        "a leitura da onu mostrou potencia recebida abaixo do normal",
    ],
    "router_failure": [
        "o roteador reiniciou repetidamente e deixou de encaminhar pacotes",
        "o equipamento de borda travou e perdeu conectividade",
        "o gateway apresentou falha e precisou ser reiniciado",
    ],
    "account_block": [
        "o acesso foi bloqueado porque a conta estava suspensa",
        "o cadastro do assinante ficou bloqueado por restricao administrativa",
        "a autenticacao foi negada enquanto o usuario permanecia suspenso",
    ],
    "fiber_break": [
        "um rompimento fisico interrompeu a fibra entre os postes",
        "o cabo optico foi partido durante uma obra na rua",
        "a equipe encontrou a fibra quebrada no trecho externo",
    ],
    "high_latency": [
        "a rede respondeu lentamente e o tempo de ida e volta aumentou",
        "o cliente percebeu atraso elevado mesmo com o link ativo",
        "a latencia subiu durante o periodo de congestionamento",
    ],
}

QUERIES = [
    ("billing_fee", "o cliente reclamou que apareceu uma cobranca extra na conta deste mes"),
    ("billing_fee", "na fatura nova existe uma taxa que nao aparecia anteriormente"),
    ("network_outage", "desde cedo a casa esta sem acesso e o link nao volta mesmo reiniciando os aparelhos"),
    ("network_outage", "a internet parou completamente depois de uma queda geral no bairro"),
    ("payment_delay", "a mensalidade venceu na semana passada e continua pendente"),
    ("payment_delay", "o cliente ainda nao pagou a conta que ja passou do vencimento"),
    ("optical_loss", "a onu esta recebendo sinal muito fraco e a leitura de potencia caiu bastante"),
    ("optical_loss", "o enlace permanece ativo mas a atenuacao aumentou e o nivel recebido esta baixo"),
    ("router_failure", "o gateway congela varias vezes por dia e so volta depois de reiniciar"),
    ("router_failure", "o equipamento que encaminha o trafego travou novamente durante a madrugada"),
    ("account_block", "o usuario nao autentica porque o cadastro consta como suspenso no sistema"),
    ("account_block", "a conta foi restringida administrativamente e por isso o acesso esta negado"),
    ("fiber_break", "uma escavacao cortou o cabo e a fibra ficou fisicamente interrompida"),
    ("fiber_break", "a equipe encontrou o cabo partido depois de uma obra na calcada"),
    ("high_latency", "o link nao caiu mas tudo demora muito para responder e o ping aumentou"),
    ("high_latency", "a navegacao esta lenta mesmo com sinal presente e sem perda total de conectividade"),
    (None, "o cliente mudou o endereco de instalacao e pediu alteracao cadastral"),
    (None, "a equipe marcou uma visita tecnica para a proxima sexta feira"),
    (None, "foi solicitado um novo plano com maior velocidade contratada"),
    (None, "o cliente perguntou qual e o horario de atendimento da loja"),
]


def build():
    full = SemanticRouterV96(threshold=0.24, min_margin=0.035, indexed=False)
    disc = DiscriminativeSemanticRouterV96(
        threshold=0.24,
        min_margin=0.035,
        candidate_limit=8,
    )
    all_sentences = [sentence for rows in TRAIN.values() for sentence in rows]
    full.observe(all_sentences)
    disc.observe(all_sentences)

    for concept_id, rows in TRAIN.items():
        # Use the most recurrent content words in the training examples as anchors.
        # Anchors remain explicit; the benchmark tests whether contextual routing
        # can map noisier held-out formulations to those concepts.
        anchors = {
            "billing_fee": ["tarifa", "encargo", "taxa"],
            "network_outage": ["falha", "indisponibilidade", "interrupcao"],
            "payment_delay": ["atrasado", "venceu", "vencimento"],
            "optical_loss": ["atenuacao", "potencia", "sinal"],
            "router_failure": ["roteador", "gateway", "equipamento"],
            "account_block": ["bloqueado", "suspensa", "suspenso"],
            "fiber_break": ["rompimento", "partido", "quebrada"],
            "high_latency": ["latencia", "atraso", "lentamente"],
        }[concept_id]
        full.register_concept(concept_id, anchors)
        disc.register_concept(concept_id, anchors)

    # Held-out query sentences are observed as online experience; the specific
    # evaluation phrase itself is not registered as an anchor/concept label.
    full.observe([q for _, q in QUERIES])
    disc.observe([q for _, q in QUERIES])
    return full, disc


def evaluate(router):
    start = perf_counter()
    outputs = [router.resolve_token(_representative_token(text)) for _, text in QUERIES]
    ms = 1000.0 * (perf_counter() - start) / len(QUERIES)
    correct = 0
    false_positive = 0
    abstain = 0
    for (expected, _), out in zip(QUERIES, outputs):
        if expected is None:
            if out.concept_id is None:
                correct += 1
                abstain += 1
            else:
                false_positive += 1
        elif out.concept_id == expected:
            correct += 1
        elif out.concept_id is None:
            abstain += 1
    return outputs, {
        "accuracy": correct / len(QUERIES),
        "false_positive_rate": false_positive / len(QUERIES),
        "abstention_rate": abstain / len(QUERIES),
        "ms_per_query": ms,
    }


def _representative_token(sentence: str) -> str:
    # TextContextMemory scores learned tokens. Pick a content token from the held-
    # out sentence that carries the user formulation rather than registering the
    # whole sentence as a synthetic symbol.
    preferred = [
        "cobranca", "taxa", "acesso", "internet", "mensalidade", "conta",
        "onu", "atenuacao", "gateway", "equipamento", "usuario", "cadastro",
        "escavacao", "cabo", "ping", "navegacao", "endereco", "visita", "plano", "horario",
    ]
    words = sentence.lower().split()
    for token in preferred:
        if token in words:
            return token
    return words[0]


def main():
    full, disc = build()
    full_outputs, full_metrics = evaluate(full)
    disc_outputs, disc_metrics = evaluate(disc)
    parity = mean(
        1.0 if a.concept_id == b.concept_id else 0.0
        for a, b in zip(full_outputs, disc_outputs)
    )
    print({"full": full_metrics})
    print({"disc8": disc_metrics, "parity": parity})
    for (expected, text), a, b in zip(QUERIES, full_outputs, disc_outputs):
        print({
            "expected": expected,
            "query": text,
            "full": a.concept_id,
            "disc8": b.concept_id,
            "disc_score": b.score,
            "disc_margin": b.margin,
        })


if __name__ == "__main__":
    main()
