from random import Random

from memoria_resolutiva.polysemy import PolysemyMemory
from memoria_resolutiva.sense_consolidation import consolidate_senses
from memoria_resolutiva.temporal_sense_consolidation_v85 import consolidate_temporal_senses

FINANCE = [
    "banco aprovou credito para cliente",
    "banco elevou taxa de juros do emprestimo",
    "cliente abriu conta no banco",
    "banco recebeu deposito e pagou rendimento",
]
DATA = [
    "banco de dados recebeu nova tabela",
    "consulta acessou indice do banco de dados",
    "servidor gravou registro no banco",
    "aplicacao atualizou coluna no banco de dados",
]
NOISE = [
    "turista sentou no banco da praca",
    "pescador descansou no banco de areia",
]


def build(seed: int, repeats: int = 8, noise_repeats: int = 1):
    rows = FINANCE * repeats + DATA * repeats + NOISE * noise_repeats
    Random(seed).shuffle(rows)
    m = PolysemyMemory(window=3, split_threshold=0.18)
    for row in rows:
        m.observe(row)
    return m


def main():
    for seed in (11, 23, 37, 57, 83, 101, 149, 211):
        m = build(seed)
        raw = len(m.senses("banco"))
        old = len(consolidate_senses(m, "banco", threshold=0.24))
        new = len(consolidate_temporal_senses(m, "banco", threshold=0.24, saturation=1.25))
        print(seed, "micro", raw, "legacy_groups", old, "temporal_groups", new)


if __name__ == "__main__":
    main()
