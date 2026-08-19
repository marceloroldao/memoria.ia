from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Iterable

from memoria_resolutiva.sentence_semantic_router_v96 import SentenceSemanticRouterV96


TRAIN = {
    "billing_fee": [
        "uma tarifa adicional apareceu na fatura mensal do cliente",
        "o provedor lancou uma taxa extra na cobranca",
        "houve cobranca de encargo que nao existia no mes anterior",
        "o valor da assinatura aumentou por causa de uma tarifa adicional",
    ],
    "network_outage": [
        "a internet caiu completamente apos indisponibilidade na rede",
        "o cliente ficou sem conexao depois de interrupcao geral do servico",
        "uma falha no enlace deixou varios assinantes offline",
        "houve queda total de conectividade no bairro durante a madrugada",
    ],
    "payment_delay": [
        "a mensalidade venceu e permanece sem pagamento",
        "a fatura esta atrasada e existe pendencia financeira",
        "o cliente nao quitou a cobranca depois da data de vencimento",
        "o pagamento continua em aberto apesar do prazo encerrado",
    ],
    "optical_loss": [
        "a potencia optica recebida pela onu caiu abaixo do normal",
        "o enlace de fibra apresentou atenuacao elevada e sinal fraco",
        "a leitura optica mostrou perda de potencia na recepcao",
        "o nivel recebido na fibra esta baixo por causa de atenuacao",
    ],
    "router_failure": [
        "o roteador travou e precisou ser reiniciado para encaminhar pacotes",
        "o gateway apresentou falha e perdeu conectividade",
        "o equipamento de borda reinicia sozinho varias vezes",
        "o roteador congelou durante o encaminhamento do trafego",
    ],
    "account_block": [
        "a conta do assinante foi suspensa e o acesso ficou bloqueado",
        "o cadastro esta restrito administrativamente e a autenticacao foi negada",
        "o usuario nao consegue autenticar porque permanece suspenso",
        "o sistema bloqueou o acesso por restricao na conta",
    ],
    "fiber_break": [
        "uma obra rompeu fisicamente o cabo de fibra na rua",
        "a equipe encontrou a fibra partida entre dois postes",
        "uma escavacao cortou o cabo optico e interrompeu o enlace",
        "o rompimento fisico da fibra ocorreu no trecho externo",
    ],
    "high_latency": [
        "a conexao continua ativa mas o ping aumentou muito",
        "a rede responde lentamente com latencia elevada",
        "o cliente percebe atraso na navegacao sem queda total do link",
        "o tempo de resposta subiu durante congestionamento",
    ],
}

CALIBRATION = [
    ("billing_fee", "apareceu uma taxa inesperada no valor cobrado neste mes"),
    ("network_outage", "desde a manha toda a regiao esta sem internet"),
    ("payment_delay", "a conta passou da data e o valor continua pendente"),
    ("optical_loss", "a potencia recebida pela onu esta fraca e caiu varios db"),
    ("router_failure", "o gateway trava e so retorna depois de reiniciar"),
    ("account_block", "o assinante consta suspenso e por isso nao autentica"),
    ("fiber_break", "a retroescavadeira cortou a fibra e o cabo ficou partido"),
    ("high_latency", "o servico nao caiu porem o ping esta alto e tudo responde devagar"),
    (None, "o cliente pediu mudanca de endereco para a instalacao"),
    (None, "foi agendada uma visita tecnica para quinta feira"),
    (None, "o assinante solicitou troca para um plano de maior velocidade"),
    (None, "a loja informou o novo horario de atendimento"),
]

TEST = [
    ("billing_fee", "o usuario questionou um encargo novo lancado na fatura"),
    ("billing_fee", "a cobranca veio maior por uma tarifa que nao reconheco"),
    ("billing_fee", "existe uma taxa adicional no boleto deste mes"),
    ("network_outage", "ninguem no predio consegue acessar a internet desde a queda"),
    ("network_outage", "o servico parou por completo e todos ficaram offline"),
    ("network_outage", "houve indisponibilidade total de conexao apos uma falha geral"),
    ("payment_delay", "a mensalidade nao foi paga e ja venceu"),
    ("payment_delay", "a cobranca continua aberta depois do vencimento"),
    ("payment_delay", "ha uma pendencia porque a fatura ficou atrasada"),
    ("optical_loss", "o sinal optico da onu esta abaixo do esperado"),
    ("optical_loss", "a fibra continua conectada mas a potencia recebida esta baixa"),
    ("optical_loss", "foi medida atenuacao alta no enlace optico"),
    ("router_failure", "o equipamento de borda congela durante o trafego"),
    ("router_failure", "o roteador reinicia repetidamente e derruba as sessoes"),
    ("router_failure", "o gateway deixou de encaminhar pacotes e travou"),
    ("account_block", "o cadastro esta suspenso e o acesso foi negado"),
    ("account_block", "a conta bloqueada impede a autenticacao do usuario"),
    ("account_block", "o assinante tem restricao administrativa no cadastro"),
    ("fiber_break", "uma obra cortou fisicamente o cabo optico"),
    ("fiber_break", "a fibra foi encontrada rompida no poste"),
    ("fiber_break", "houve quebra do cabo apos escavacao na calcada"),
    ("high_latency", "a internet esta ativa mas o ping ficou muito alto"),
    ("high_latency", "nao houve queda porem a navegacao esta com grande atraso"),
    ("high_latency", "o tempo de resposta da rede aumentou bastante"),
    (None, "o cliente deseja cancelar o contrato no proximo mes"),
    (None, "o tecnico substituiu a fonte de alimentacao da onu"),
    (None, "foi solicitado um segundo ponto de wifi dentro da casa"),
    (None, "o usuario quer atualizar telefone e email do cadastro"),
    (None, "a equipe confirmou visita para amanha a tarde"),
    (None, "o cliente perguntou sobre os planos disponiveis"),
    (None, "a loja fechara mais cedo no feriado"),
    (None, "foi emitido um comprovante de pagamento ja realizado"),
]


@dataclass(frozen=True, slots=True)
class Metrics:
    accuracy: float
    positive_recall: float
    false_positive_rate: float
    abstention_rate: float
    wrong_known_class_rate: float


def build(threshold: float, min_margin: float) -> SentenceSemanticRouterV96:
    router = SentenceSemanticRouterV96(threshold=threshold, min_margin=min_margin)
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    return router


def evaluate(router: SentenceSemanticRouterV96, rows: Iterable[tuple[str | None, str]]):
    rows = list(rows)
    correct = false_positive = abstention = wrong_known = positive = positive_ok = 0
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    outputs = []
    for expected, sentence in rows:
        result = router.resolve(sentence)
        predicted = result.concept_id
        matrix[str(expected)][str(predicted)] += 1
        outputs.append((expected, sentence, result))
        correct += int(predicted == expected)
        if expected is None:
            false_positive += int(predicted is not None)
        else:
            positive += 1
            positive_ok += int(predicted == expected)
            abstention += int(predicted is None)
            wrong_known += int(predicted is not None and predicted != expected)
    n = len(rows)
    return Metrics(
        accuracy=correct / n,
        positive_recall=positive_ok / positive if positive else 0.0,
        false_positive_rate=false_positive / n,
        abstention_rate=abstention / n,
        wrong_known_class_rate=wrong_known / n,
    ), matrix, outputs


def calibrate():
    best = None
    for ti in range(5, 31):
        threshold = ti / 100
        for mi in range(0, 16):
            min_margin = mi / 100
            router = build(threshold, min_margin)
            metrics, _, _ = evaluate(router, CALIBRATION)
            # Strongly penalize open-set false positives and wrong known-class
            # predictions. Calibration never sees TEST.
            objective = (
                metrics.accuracy
                - 2.0 * metrics.false_positive_rate
                - 2.0 * metrics.wrong_known_class_rate
            )
            candidate = (objective, metrics.accuracy, -metrics.false_positive_rate,
                         threshold, min_margin)
            if best is None or candidate > best:
                best = candidate
    assert best is not None
    return best[-2], best[-1]


def main():
    threshold, margin = calibrate()
    router = build(threshold, margin)
    metrics, matrix, outputs = evaluate(router, TEST)
    print({"threshold": threshold, "min_margin": margin})
    print(metrics)
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))
    print("errors")
    for expected, sentence, result in outputs:
        if result.concept_id != expected:
            print({
                "expected": expected,
                "predicted": result.concept_id,
                "score": result.score,
                "margin": result.margin,
                "sentence": sentence,
            })


if __name__ == "__main__":
    main()
