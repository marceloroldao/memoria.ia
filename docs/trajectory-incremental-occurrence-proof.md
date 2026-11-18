# Atualização incremental de ocorrências conhecidas

## Comportamento

Uma ocorrência nova de conteúdo já conhecido atualiza a projeção ativa sem
reconstruir seu histórico. O catálogo de composições permanece fixo; spans e
perfis desse payload são reutilizados. O evento avança a ordem de sua captura,
forma pares inéditos e registra testemunhas de ocorrências, sem novo voto de
conteúdo ou reforço de pares já vistos. Esquecimento continua usando ticks de
ocorrência, inclusive para cópias.

Conteúdo novo invalida a projeção e o catálogo na hierarquia afetada. A próxima
leitura reconstrói ambos e projeta os nódulos recém-descobertos sobre o passado.
Reexecutar o mesmo ID não atualiza a projeção. Se a projeção foi descartada ao
consultar outra hierarquia, ela é reconstruída a partir das observações.

O método interno `append_known_occurrence` rejeita um payload desconhecido ou
com símbolos alterados antes de mutar a projeção. O gerador continua responsável
pela validação dos IDs e pelo isolamento de hierarquias. Consultas permanecem
sem aprendizado; apenas `observe` atualiza os dados derivados.

## Retenção e ordem

Cada profundidade retém o perfil projetado de cada payload conhecido e a cauda
de eventos de cada captura, limitada ao horizonte temporal do campo. Os ticks
absolutos são mantidos separadamente: podar a cauda não renumera testemunhas
nem permite unir ocorrências intermediárias diferentes. Pesos e testemunhas
acumulados não são removidos por essa poda.

Isso não limita toda a RAM: perfis, votos e conjuntos de testemunhas continuam
dependendo do volume de conteúdo e relações. Nenhum cache derivado é persistido;
a reabertura continua usando o snapshot de conteúdo e observações.

## Prova local — 30/09/2026 UTC

- 59 testes do gerador passaram, incluindo atualização sem reconstrução ou
  reprojeção, rejeição de conteúdo alterado/desconhecido e horizonte podado com
  ticks absolutos e paridade de caminhos.
- Dois lotes intercalados passaram nos 192 ciclos anteriores. Eles agora exigem
  zero reconstruções e zero projeções de spans para conteúdo reutilizado.
- `trajectory_incremental_probe.py` passou em mais 118 ciclos de sequências
  longas, incluindo B→C antes de A→B, mais de um horizonte de repetições,
  A→B→C na mesma captura, conteúdo novo e troca de hierarquia ativa.
- Cada ciclo compara resultados completos com a reconstrução fria do snapshot
  e com leitura aquecida. A comparação inclui testemunhas de ocorrência que a
  igualdade normal das dataclasses desconsidera. Consultas não alteram snapshot
  ou estado de aprendizado.
- Dois digests de referência foram gerados **pela implementação anterior** do
  commit `544e8ff8c969fc9790db3e225c4f494f492a400d`, carregada em módulos isolados.
  A implementação incremental reproduz os mesmos digests. Somente essa prova
  entre ambientes arredonda floats a 12 casas; a paridade fria local é exata.
  A referência está em `benchmark-results/trajectory-incremental-reference.json`.
- Todos os lotes anteriores de contextos, episódios, online, estabilidade e
  adaptador sintético de export passaram. A regressão pytest é verificada no
  workflow remoto, pois pytest não está disponível localmente.

## Medição sintética

Com 128 payloads iniciais e oito ciclos por carga:

| Carga | Reconstruções antes → agora | Spans projetados antes → agora | Ciclo total antes → agora (s) |
| --- | --- | --- | --- |
| Conteúdo novo | 8 → 8 | 1.060 → 1.060 | 0,267410 → 0,283121 |
| Reuso com novos pares | 8 → 0 | 1.060 → 0 | 0,222305 → 0,106843 |
| Mesmo par | 8 → 0 | 1.060 → 0 | 0,245979 → 0,118443 |
| Mesmo ID | 0 → 0 | 0 → 0 | 0,102969 → 0,098214 |

Tempos incluem ingestão, leitura e profiler; são descritivos e sujeitos à
variação entre execuções. A carga com conteúdo novo não ganhou em contagem
e foi mais lenta nesta amostra. O gate exige paridade e contagens, não uma
velocidade dependente da máquina. A atualização transferiu parte do trabalho
para a ingestão; os perfis registram os dois custos separadamente.

Resultados completos:

- [Lote inicial](../benchmark-results/trajectory-incremental-interleaved.json).
- [Segundo lote](../benchmark-results/trajectory-incremental-heldout.json).
- [Sequências longas](../benchmark-results/trajectory-incremental-long-proof.json).

## Validação remota

O [workflow dedicado](https://github.com/marceloroldao/memoria.ia/actions/runs/36667186015)
passou no commit `d1467deaffe63115582b076e8f0754cd06ab1e43`: 59 testes do
gerador, 66 regressões, os dois lotes intercalados, a referência anterior e
todos os controles anteriores passaram. Um teste de BDR nativo opcional foi
pulado. Os 12 arquivos publicados foram conferidos como idênticos aos arquivos
validados localmente.

## Limites

Esta atualização atende ocorrências de conteúdo conhecido sob catálogo fixo.
Conteúdo novo continua exigindo reconstrução completa. Não há execução em
segundo plano, atualização incremental da descoberta de nódulos, validação em
Android, medição de RAM ou teste de concorrência nesta etapa. A geração mantém
as mesmas regras de ambiguidade e não promove proximidade a fato. O PR #374
permanece rascunho, fora do OFF.IA, com os três gates pessoais nativos pendentes.
