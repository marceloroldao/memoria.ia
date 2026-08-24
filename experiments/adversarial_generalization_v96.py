from __future__ import annotations

import importlib.util
import sys
from collections import Counter, defaultdict
from pathlib import Path

from memoria_resolutiva.trajectory_contrastive_v96 import TrajectoryContrastiveRouterV96

_HERE = Path(__file__).resolve().parent
_SPLIT_PATH = _HERE / "natural_language_split_v96.py"
_spec = importlib.util.spec_from_file_location("natural_language_split_v96_adversarial", _SPLIT_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load benchmark dataset: {_SPLIT_PATH}")
_split = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = _split
_spec.loader.exec_module(_split)
TRAIN = _split.TRAIN

# Deliberately written independently from the original held-out TEST.
# Categories: paraphrase, typo/noise, incomplete context, negation/near-miss,
# neighboring concepts, and difficult open-set negatives.
ADVERSARIAL = [
    # billing_fee
    ("billing_fee", "veio um valor extra na conta deste mes que antes nao aparecia"),
    ("billing_fee", "tem uma cobranca nova no boleto e nao sei de onde saiu"),
    ("billing_fee", "tarifa inesperda apareceu na fatura"),
    ("billing_fee", "me cobraram um adicional na mensalidade"),
    ("billing_fee", "o preco do servico nao caiu, aumentou por uma taxa nova"),
    ("billing_fee", "encargo extra no boleto"),

    # network_outage
    ("network_outage", "a conexao sumiu para todo mundo aqui no condominio"),
    ("network_outage", "desde cedo estamos totalmente sem acesso a rede"),
    ("network_outage", "internet caiu geral e n volta"),
    ("network_outage", "sem conexao em todas as casas da rua"),
    ("network_outage", "nao e lentidao, o link parou completamente"),
    ("network_outage", "queda total do servico"),

    # payment_delay
    ("payment_delay", "o boleto venceu ontem e ainda nao foi pago"),
    ("payment_delay", "continua faltando quitar a mensalidade"),
    ("payment_delay", "fatura atrazada permanece em aberto"),
    ("payment_delay", "pagamento pendente depois do vencimento"),
    ("payment_delay", "nao houve quitacao e o prazo ja terminou"),
    ("payment_delay", "mensalidade vencida"),

    # optical_loss
    ("optical_loss", "rx da onu despencou e o sinal de fibra ficou fraco"),
    ("optical_loss", "medicao mostra potencia optica muito abaixo do normal"),
    ("optical_loss", "atenuacao alta no enlace de fibra"),
    ("optical_loss", "sinal optco baixo na onu"),
    ("optical_loss", "a fibra nao rompeu mas a recepcao esta fraca"),
    ("optical_loss", "perda de potencia optica"),

    # router_failure
    ("router_failure", "o roteador para de responder ate reiniciar"),
    ("router_failure", "gateway congela quando passa trafego"),
    ("router_failure", "equipamento reiniciando sozinho toda hora"),
    ("router_failure", "roteador trvou e nao encaminha pacotes"),
    ("router_failure", "o link existe mas o gateway deixou de funcionar"),
    ("router_failure", "gateway travado"),

    # account_block
    ("account_block", "usuario suspenso nao consegue entrar no sistema"),
    ("account_block", "autenticacao recusada por restricao administrativa"),
    ("account_block", "conta bloqueda impede acesso"),
    ("account_block", "cadastro suspenso"),
    ("account_block", "a senha esta certa mas a conta continua bloqueada"),
    ("account_block", "acesso negado por suspensao"),

    # fiber_break
    ("fiber_break", "caminhao arrancou o cabo de fibra no poste"),
    ("fiber_break", "o cabo optico esta fisicamente partido"),
    ("fiber_break", "escavadeira cortou a fbra na rua"),
    ("fiber_break", "rompimento de fibra entre dois postes"),
    ("fiber_break", "nao e apenas sinal fraco, o cabo foi seccionado"),
    ("fiber_break", "fibra cortada"),

    # high_latency
    ("high_latency", "abre tudo muito devagar embora a conexao continue de pe"),
    ("high_latency", "ping disparou mas nao houve queda"),
    ("high_latency", "rede lenta com tempo de resposta enorme"),
    ("high_latency", "latencia mto alta"),
    ("high_latency", "a internet funciona, so responde com atraso"),
    ("high_latency", "ping alto"),

    # difficult open-set / near misses
    (None, "o pagamento foi feito hoje e o comprovante esta anexado"),
    (None, "quero saber como emitir segunda via da fatura"),
    (None, "a onu foi trocada por um modelo novo e esta funcionando normalmente"),
    (None, "o tecnico limpou os conectores opticos preventivamente"),
    (None, "preciso alterar o email cadastrado na conta"),
    (None, "o usuario trocou a senha com sucesso"),
    (None, "foi instalada uma nova caixa de emenda na fibra"),
    (None, "a equipe vai remanejar o cabo para outro poste"),
    (None, "o cliente pediu um roteador com wifi mais moderno"),
    (None, "o roteador recebeu atualizacao de firmware sem apresentar falha"),
    (None, "o plano contratado foi aumentado de velocidade"),
    (None, "o cliente perguntou qual e a velocidade nominal do plano"),
    (None, "a rede ficou lenta porque o celular estava atualizando varios aplicativos"),
    (None, "houve uma manutencao programada que ainda nao comecou"),
    (None, "o boleto ainda nao venceu e sera pago na proxima semana"),
    (None, "a potencia optica foi medida e esta dentro da faixa normal"),
]

COUNTEREXAMPLES = {
    "payment_delay": [
        "foi emitido um comprovante de pagamento ja realizado",
        "o cliente apresentou recibo de uma fatura que ja foi quitada",
    ],
    "optical_loss": [
        "o tecnico substituiu a fonte de alimentacao da onu",
        "a onu recebeu uma nova fonte eletrica durante manutencao",
    ],
    "account_block": [
        "o usuario quer atualizar telefone e email do cadastro",
        "o cliente solicitou apenas alteracao cadastral sem bloqueio de acesso",
    ],
}


def build() -> TrajectoryContrastiveRouterV96:
    router = TrajectoryContrastiveRouterV96(
        threshold=0.12,
        min_margin=0.02,
        negative_threshold=0.20,
        min_contrast_margin=0.04,
    )
    for concept_id, examples in TRAIN.items():
        router.observe_concept(concept_id, examples)
    for concept_id, examples in COUNTEREXAMPLES.items():
        for sentence in examples:
            router.observe_counterexample(concept_id, sentence)
    return router


def main() -> None:
    router = build()
    matrix: dict[str, Counter[str]] = defaultdict(Counter)
    positive = positive_ok = false_positive = wrong_known = abstained = 0
    errors_by_kind: Counter[str] = Counter()

    for expected, sentence in ADVERSARIAL:
        result = router.resolve(sentence)
        predicted = result.concept_id
        matrix[str(expected)][str(predicted)] += 1
        if expected is None:
            false_positive += int(predicted is not None)
        else:
            positive += 1
            positive_ok += int(predicted == expected)
            wrong_known += int(predicted is not None and predicted != expected)
            abstained += int(predicted is None)
        if predicted != expected:
            kind = "open_set_fp" if expected is None else ("known_abstention" if predicted is None else "wrong_known")
            errors_by_kind[kind] += 1
            print({
                "kind": kind,
                "expected": expected,
                "predicted": predicted,
                "source": result.source,
                "positive_score": result.positive_score,
                "negative_score": result.negative_score,
                "contrast_margin": result.contrast_margin,
                "sentence": sentence,
            })

    negatives = sum(1 for expected, _ in ADVERSARIAL if expected is None)
    n = len(ADVERSARIAL)
    correct = sum(matrix[k][k] for k in matrix)
    metrics = {
        "n": n,
        "known_queries": positive,
        "open_set_queries": negatives,
        "accuracy": correct / n,
        "known_recall": positive_ok / positive if positive else 0.0,
        "open_set_false_positive_rate": false_positive / negatives if negatives else 0.0,
        "wrong_known_class_rate": wrong_known / positive if positive else 0.0,
        "known_abstention_rate": abstained / positive if positive else 0.0,
        "errors_by_kind": dict(errors_by_kind),
    }
    print("adversarial_generalization_v96")
    print(metrics)
    print("confusion_matrix")
    for expected in sorted(matrix):
        print(expected, dict(matrix[expected]))

    # Loose sanity gates: this is deliberately harder than calibration/test and is
    # meant to expose weaknesses, not encode the current desired result as a test.
    if metrics["known_recall"] < 0.50:
        raise SystemExit("known recall collapsed below 0.50")
    if metrics["wrong_known_class_rate"] > 0.35:
        raise SystemExit("wrong-known-class rate exceeded 0.35")


if __name__ == "__main__":
    main()
