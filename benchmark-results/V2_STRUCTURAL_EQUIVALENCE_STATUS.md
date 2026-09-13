# V2 structural equivalence — status inicial

Data: 2026-09-10

## Origem

A comparação formal contra a baseline restart3 qualificada mostrou:

- restart3 resolve o fixture persistente `qual nome dos meus gatos?` retornando a coleção estável contendo Lotus e excluindo Vibe;
- V2 preserva e recupera controles estruturais próximos (`eu tenho um gato que se chama` -> Lotus; `ele tem um irmão, que se chama` -> Vibe);
- V2 não resolve ainda a reformulação plural do restart3;
- V2 manteve consulta read-only e determinismo após restart no probe compartilhado.

## Decisão

Não adicionar regras lexicais/semânticas ao motor para fazer a V2 vencer o fixture. Abrir experimento de equivalência estrutural emergente (#298), baseado em convergência de trajetórias independentes.

## Gate epistemológico mínimo adicionado

Antes de integrar ao resolver:

1. convergência repetida por linhagens independentes pode suportar equivalência;
2. repetição da mesma linhagem não é confirmação independente;
3. uma convergência acidental única é insuficiente.

Arquivos iniciais:

- `docs/V2_STRUCTURAL_EQUIVALENCE.md`
- `benchmarks/structural_equivalence_v2_probe.py`
- `tests/test_structural_equivalence_v2_probe.py`

## Próximos gates

- divergência posterior/revogação;
- hub denso;
- equivalências conflitantes;
- persistência/restart;
- consulta read-only;
- escala 100/1k/10k;
- integração opt-in no resolver multiescala;
- repetir fixture restart3 sem conhecimento lexical específico.

Nenhum resultado desta linha autoriza merge em `main` ou substituição de restart3.
