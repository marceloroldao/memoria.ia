# Consulta intercalada com aprendizado e reuso do catálogo

## Medição e alteração

O cache de projeção do commit `d2f70cb` elimina reconstruções em consultas
sem novas ocorrências. O ciclo consultar → observar → consultar revelou
outro custo: o catálogo hierárquico era redescoberto em cada geração e em
cada reconstrução da projeção, mesmo sem alteração do conteúdo único.

O experimento agora retém também o catálogo imutável da última hierarquia
consultada. Somente um payload ainda não aprendido nessa hierarquia invalida
esse catálogo. Uma ocorrência de payload já conhecido continua invalidando
a projeção temporal: ordem, pares inéditos, esquecimento e caminhos precisam
ser recalculados. O catálogo e a projeção têm, portanto, ciclos diferentes.

Nenhum dos dois entra no snapshot. Cada cache retém no máximo uma hierarquia;
trocar a hierarquia consultada substitui sua entrada. Uma nova observação em
outra hierarquia não invalida o catálogo ativo. Os níveis retornados contêm
dataclasses congeladas e tuplas; não acrescentam votos de conteúdo.

## Prova sintética local — 30/09/2026 UTC

`scripts/trajectory_interleaved_probe.py` verifica quatro cargas sobre 16,
48 e 128 payloads iniciais, com oito ciclos por carga. Cada ciclo compara
evocação, estabilidade, caminhos e geração com uma reconstrução fria do
snapshot e com nova leitura aquecida. A comparação serializada inclui as
testemunhas de ocorrências que a igualdade normal das dataclasses ignora.
As consultas não alteram snapshot ou estado de aprendizado.

Os lotes `20260930` e `20261002` passaram em 12 cenários cada: 96 ciclos por
lote e 192 ciclos no total. Passaram também 56 testes do gerador, incluindo
um controle novo de reuso, descoberta de composição após conteúdo novo,
isolamento de hierarquias e substituição do catálogo ativo.

Contagens por cenário de oito ciclos, iguais nos três tamanhos:

| Carga | Catálogos antes | Catálogos agora | Projeções temporais agora |
| --- | ---: | ---: | ---: |
| Conteúdo novo em cada ciclo | 16 | 8 | 8 |
| Conteúdo reutilizado formando novos pares | 16 | 0 | 8 |
| Repetições do mesmo par | 16 | 0 | 8 |
| Reexecução do mesmo ID | 8 | 0 | 0 |

Exemplo de tempos **com profiler**, com 128 payloads iniciais; não são latência
de produção nem garantia de velocidade:

| Carga | Leitura antes (s) | Leitura agora (s) |
| --- | ---: | ---: |
| Conteúdo novo | 0,291018 | 0,257005 |
| Reuso com novos pares | 0,274350 | 0,220316 |
| Mesmo par | 0,273136 | 0,244130 |
| Mesmo ID | 0,113675 | 0,102426 |

Relatórios completos, incluindo custos de ingestão e funções mais caras:

- [Baseline d2f70cb](../benchmark-results/trajectory-interleaved-baseline-d2f70cb.json).
- [Catálogo reutilizado](../benchmark-results/trajectory-interleaved-catalogue-reuse.json).
- [Segundo lote](../benchmark-results/trajectory-interleaved-heldout-20261002.json).

A baseline foi executada com a classe do commit `d2f70cb` carregada em um
módulo isolado, usando os mesmos cenários e comparações frias. A versão atual
exige as contagens da tabela, sem impor limiares de tempo dependentes da máquina.

## Limites e próximo trabalho

Esta é uma redução de redescoberta de conteúdo, não atualização incremental
das relações temporais. Toda ocorrência com ID novo ainda reconstrói a
projeção. Com 128 payloads iniciais, oito ciclos de qualquer dessas cargas
ainda fizeram 1.060 projeções de spans; o histórico continua sendo percorrido.
O custo também permanece nas consultas de relações e na busca de continuações.

Não foi medido uso de RAM, Android, produção ou execução concorrente.
Os três gates pessoais nativos e a integração do gerador no OFF.IA seguem
pendentes. O PR #374 permanece rascunho. O próximo alvo é projetar ocorrências
novas sobre um catálogo estável, com reconstrução completa quando a descoberta
de conteúdo modificar esse catálogo. A junção por ocorrência exata e a descoberta
retrospectiva de nódulos devem permanecer nos controles dessa futura alteração.
