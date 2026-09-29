# Replay estrutural de um export do OFF.IA

Em 28/09/2026, executamos o experimento Python com um export real de entradas
do OFF.IA, apenas para leitura. O script não publica textos pessoais, IDs da
origem nem o JSON original. Reproduzir com um arquivo local autorizado:

```sh
python scripts/trajectory_private_replay.py --export /caminho/privado/export.json
```

Sem `--export`, o script executa um exemplo sintético que também roda no CI.
O adaptador tokeniza aproximadamente como a versão nativa v1, dobra caixa e
atribui endereços inteiros opacos aos tokens. A equivalência exata com a
tokenização do APK não foi demonstrada. O replay preserva a ordem do export,
separa as capturas e alimenta o experimento somente com as entradas do usuário.
As cópias exatas normalizadas criam ocorrências sem voto de **conteúdo**; uma
ocorrência pode testemunhar um par temporal ainda inédito.

As medidas a seguir registram as etapas anteriores à inclusão das ocorrências
repetidas no relógio das raízes. A seção final traz o estado atual.

| Medida agregada | Resultado |
| --- | ---: |
| Observações estruturais / capturas | 99 / 28 |
| Payloads normalizados distintos | 68 |
| Ocorrências duplicadas sem voto de conteúdo | 31 |
| Payloads distintos que têm cópias | 9 |
| Endereços opacos de tokens | 140 |
| Consultas inéditas com prefixo e sufixo, uma por payload distinto | 68 |
| Modos após união anterior: só nódulo / só raiz / ambos / eco | 9 / 18 / 30 / 11 |
| Modos com recuo a pistas menores: só nódulo / só raiz / ambos / eco | 14 / 17 / 31 / 6 |
| Modos após recuo de raiz embutida sem sucessor: só nódulo / só raiz / ambos / eco | 13 / 17 / 32 / 6 |
| Consultas com raiz menor ligada além da maior / destino adicional | 1 / 1 |
| Novos destinos na geração / novos casos ambíguos / novos truncamentos | 1 / 0 / 0 |
| Após verificação de nódulos menores: destinos novos / seleções suspensas | 7 / 2 |
| Após verificação de nódulos menores: ambíguas / truncadas / saídas únicas | 55 / 19 / 7 |
| Ambos com destinos disjuntos / algum destino comum | 31 / 1 |
| Consultas com ambiguidade, antes / agora | 47 / 53 |
| Consultas com truncamento, antes / agora | 13 / 15 |
| Saídas únicas diferentes de eco, antes / agora | 10 / 9 |
| Consultas com rotas recorrentes / ambíguas, antes / agora | 39 / 27 → 45 / 33 |
| Liderança estrutural sem empate / entre duas ou mais capturas, agora | 35 / 6 |
| Máximo de capturas independentes para uma rota | 5 |

Uma segunda passagem consulta **cada entrada original antes de aprendê-la**.
Ela usa a mesma tabela fixa de endereços opacos para tokens, mas cada consulta
vê somente as observações anteriores. Das 99 consultas online, antes do recuo
a pistas menores houve 53 ecos, 4 só continuações, 12 combinações de
continuação e evocação, 22 só evocações de nódulo e 8 combinações de
evocações. Agora são 40 ecos, 4 continuações, 12 combinações com continuação,
35 evocações de nódulo e 8 combinações de evocações. São 57 consultas
ambíguas, 9 truncadas e 2 saídas estruturais únicas diferentes de eco
(antes: 44, 8 e 2). O recuo substitui 13 ecos por evocações em entradas
reais, mas não existe rótulo de resposta para avaliá-las. Esses números
medem modos de operação, não acertos.

A medição `route_stability` encontra um primeiro colocado estrutural em 35
consultas, mas somente 6 deles são testemunhados em duas ou mais capturas.
Esse contraste impede interpretar automaticamente o maior peso como consenso.
Detalhes e controles estão na
[prova de estabilidade](trajectory-stability-proof.md).

O recuo da raiz embutida alterou uma das 68 consultas inéditas: ela agora
exibe candidatos tanto de nódulo recorrente quanto de raiz contida, em vez
de mostrar apenas o nódulo. As 99 consultas cronológicas e a avaliação do
único par explícito não mudaram. Esse novo candidato também pode ser uma
distração; o export não tem rótulos suficientes para medir acurácia.

Na comparação seguinte, manter também raízes menores **já ligadas** acrescentou
um destino em uma das 68 consultas inéditas. Nenhum modo, seleção, contagem de
ambiguidade ou truncamento mudou: a consulta já tinha alternativas. As 99
consultas cronológicas e o único par explícito mantiveram seus agregados.
Essa rota adicional tem testemunha de ordem na captura; o export não informa
se ela seria uma resposta adequada.

A verificação de nódulos recorrentes menores encontrou **7 consultas inéditas
com destino adicional** e retirou `selected` de **2** que antes pareciam ter
uma rota única. Os modos permanecem 13 só nódulo, 17 só raiz, 32 combinados e
6 ecos. Ambiguidade passa de 53 para 55 e truncamento de 15 para 19; 7 saídas
estruturais únicas diferentes de eco permanecem. Uma expansão completa em
todas as consultas truncaria 27 leituras de associação, por isso ela fica
disponível como diagnóstico e a geração a usa quando uma rota parece única.
Na passagem cronológica, as 99 consultas mantêm os mesmos modos e 2 saídas
únicas, com truncamento de 9 para 11. A avaliação do único par explícito não
muda. Sem mais rótulos, não sabemos se as 7 rotas adicionais ajudam ou
distraem em uma resposta.

O export contém **um** `reply_to` explícito resolúvel. Ele foi usado **só
depois** do aprendizado para conferir a evocação; não foi passado a `observe`
nem a `generate`. Sua pergunta de origem e o destino observado aparecem uma
vez cada. Em uma consulta inédita que contém a pergunta inteira, a execução
sem a nova evocação de raiz embutida deu `ECHO`; com ela, o destino observado
apareceu como candidato único (`EMBEDDED_TEMPORAL_RECALL`), sem ambiguidade
ou truncamento. Um prefixo inédito terminado na mesma pergunta também evoca
esse destino. O modo indica sucessão testemunhada na mesma captura, não
confirma que o destino seja uma resposta verdadeira.

O único par vinculado está nas **duas últimas observações** do export. Na
passagem cronológica, consultar a pergunta envolta em um contexto novo logo
após a origem ainda dá `ECHO`; antes de aprender o destino também dá `ECHO`.
Somente depois de observar o destino ela produz o candidato único. Portanto,
esse par comprova recuperação de uma sequência já observada, **não** previsão
de uma resposta ainda não vista ou estabilidade após futuras entradas. A
[prova cronológica sintética](trajectory-episode-proof.md#prova-cronológica-de-evocação)
verifica o comportamento online com novos contextos e uma entrada interposta.

Entre as nove consultas sobre payloads com cópias, três expõem as duas
famílias de rotas, quatro evocam só nódulo recorrente e duas dão eco. As cópias
não reforçaram pesos. As 10 saídas únicas anteriores caíram para 9 porque
alternativas antes encobertas agora impedem uma seleção estrutural única.
Isso não é uma medida de acerto: só um par possui avaliação explícita, e as
demais rotas podem ser irrelevantes. A raiz inteira aparece primeiro, porém
o método preserva os concorrentes e não soma os pesos de famílias diferentes.
A ordenação entre famílias ainda não foi calibrada; mais alternativas podem
ser distrações, e duas consultas adicionais sinalizam truncamento.

Isso prova uma capacidade estrutural pequena no host Python, com um caso real
rotulado pelo export. O aplicativo OFF.IA não usa esse gerador, o gate pessoal
nativo ainda tem três casos pendentes, e não há evidência de compreensão
factual, desempenho geral em diálogos ou processamento em segundo plano.

## Ocorrências repetidas na ordem temporal das raízes (29/09/2026)

O experimento agora conserva todas as 99 posições da ordem das 28 capturas
para evocar relações entre raízes. Os 68 payloads normalizados distintos
continuam armazenados uma vez, e as 31 cópias não reforçam o conteúdo. Uma
cópia pode formar um **par ordenado novo** com um payload anterior da mesma
captura; cada par tem no máximo um testemunho por hierarquia. Na leitura deste
export, nasceram 176 pares: 155 em entradas de conteúdo distinto e 21 em
ocorrências de conteúdo reutilizado. Os pares não foram passados manualmente.

| Leitura agregada | Antes | Com ocorrências na ordem |
| --- | ---: | ---: |
| 68 consultas inéditas: só nódulo / só raiz / ambos / eco | 13 / 17 / 32 / 6 | 8 / 18 / 37 / 5 |
| 68 consultas inéditas: ambíguas / truncadas / únicas sem eco | 55 / 19 / 7 | 56 / 24 / 7 |
| 99 consultas antes de observar a entrada: eco / continuação / continuação e evocação | 40 / 4 / 12 | 39 / 4 / 12 |
| 99 consultas antes de observar: só nódulo / combinações de evocação / só raiz temporal | 35 / 8 / 0 | 16 / 27 / 1 |
| 99 consultas antes de observar: ambíguas / truncadas / únicas sem eco | 57 / 11 / 2 | 57 / 22 / 3 |

O único `reply_to` explícito permanece uma checagem retrospectiva: antes do
destino observado ainda há eco; depois, a consulta que contém a origem evoca
esse destino como candidato único. O aumento de rotas também elevou os casos
truncados, sobretudo na passagem cronológica. O export não traz rótulos para
decidir se as outras rotas novas ajudam ou distraem. O suporte de nódulos
intermediários ainda usa payloads distintos e não incorporou essas cópias.
