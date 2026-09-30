# Experimento de geração por trajetórias

## Objetivo e estado

Primeiro experimento executável da direção definida em 27/09/2026: aprender
automaticamente com entradas, preservar símbolos e nódulos em diferentes
escalas, repetir quando não houver rota e expor continuações concorrentes.
Nenhuma etapa requer `reply_to`, vínculos manuais, predicados linguísticos,
rotulação de verdade ou uma LLM externa.

O módulo Python `trajectory_generation_v2.py` usa o índice de trajetórias,
o motor de composições hierárquicas e o campo contínuo já existentes. É uma
camada experimental de hipóteses. A recuperação factual/ocorrencial anterior
continua com seu contrato; o aplicativo OFF.IA e seu APK ainda não usam este
gerador. Os três casos pendentes do gate pessoal anterior permanecem pendentes.

Executar, sem dependências opcionais:

```sh
python scripts/trajectory_generation_gate.py
```

O comando executa os testes e imprime exemplos sintéticos em JSON. Também há
um workflow específico, `trajectory generation proof`, para o experimento e
a regressão dos consumidores do índice alterado.

## O que é armazenado

O núcleo recebe sequências de endereços inteiros opacos. O adaptador da
demonstração usa pontos de código Unicode; os testes também usam bytes e
renomeações arbitrárias dos endereços. Espaços, acentos e posições repetidas
são preservados. Não há normalização de caixa, Unicode ou paráfrases.
Adaptadores de modalidades diferentes precisam fornecer endereços com origem
bem definida ou hierarquias distintas; compartilhar um número não demonstra
equivalência entre um pixel, um byte e uma letra.

1. O endereço do payload é calculado sobre sua sequência completa.
2. Um payload idêntico usa a mesma raiz. Uma nova ocorrência guarda só a
   referência e a origem. Reexecutar o mesmo identificador de ocorrência é
   idempotente; reutilizá-lo com dados diferentes é erro.
3. Na primeira gravação de um payload diferente, os maiores payloads já
   conhecidos contidos nele são referenciados; somente o restante é escrito
   como símbolos.
4. Exemplo: `qual nome do meu pai?` vira N1. A segunda entrada fica
   `poderia me dizer ` + referência a N1. A expansão reconstrói exatamente a
   entrada original, inclusive símbolos adjacentes iguais.
5. O estado durável é uma tabela de nódulos e uma lista de ocorrências que
   apontam para ela. Índices expandidos e campos são derivados reconstruíveis.

Essa primeira representação reutiliza **payloads completos já conhecidos**
como subtrechos. Subtrechos menores recorrentes também formam composições
derivadas; a recompactação retroativa do armazenamento por essas novas
composições fica para uma etapa posterior. Não se promete compressão ótima.

## Quando aprende

Dentro de uma hierarquia, o mesmo conteúdo completo contribui uma única vez:
cópias não aumentam seus pesos, suporte ou número de trajetórias. Cada
ocorrência, inclusive de conteúdo já conhecido, ocupa uma posição na ordem
da sua captura. Se um payload conhecido vier depois de outro com o qual ainda
não havia um par ordenado, esse **par novo** ganha uma relação; repetir o
mesmo par não lhe dá outro voto. Uma hierarquia nova aprende separadamente,
compartilhando a tabela de conteúdo armazenado.

Uma entrada diferente que contém N1 é um novo contexto. Ela aumenta o suporte
das rotas compartilhadas e cria relações com o entorno. A estrutura de N1
permanece imutável. Distintos payloads não significam fontes independentes
nem fatos corroborados: adicionar um prefixo irrelevante ainda cria conteúdo
distinto neste experimento. Não há deduplicação semântica.

`respond` consulta a memória anterior e depois observa apenas a entrada
externa. A resposta gerada não é reinserida. `generate` e as inspeções são
somente leitura, inclusive para hierarquias desconhecidas.

## Pesos explícitos

| Relação | Regra inicial | Uso |
| --- | --- | --- |
| Próximo endereço após um contexto | Número de payloads distintos que testemunham a opção / soma desses suportes | Peso relativo na geração; produto acumulado em log |
| Símbolos separados por distância d dentro de uma entrada nova | `exp(-0.35 * (d - 1))` por ocorrência posicional | Campo de associação inspecionável |
| Raízes em duas ocorrências separadas por k posições na mesma captura | `exp(-0.35 * (k - 1))`, só no primeiro testemunho do par ordenado por hierarquia | Evocação temporal de payloads |
| Entradas de conteúdo novo separadas por k eventos no campo de símbolos | `exp(-0.35 * (k - 1))` | Associação temporal entre símbolos |
| Símbolos entre entradas | Kernel temporal multiplicado pelas frequências normalizadas dos símbolos em cada entrada | Associação temporal inspecionável |
| Esquecimento | Desativado por padrão (`forgetting_rate=0`) | Configurável, ainda sem calibração empírica |

O suporte de continuação conta no máximo um voto por payload e próximo
endereço; um payload pode testemunhar opções diferentes em posições distintas.
O campo de distância registra ocorrências posicionais, preservando inclusive
autorrelações. São medidas diferentes e são expostas separadamente.

Os parâmetros são hipóteses de engenharia, não pesos aprendidos por gradiente
ou valores biologicamente validados. Os pesos de distância entre símbolos
ainda não são combinados com o escore de continuação. Os pares ordenados de
raízes fornecem evocação temporal quando a continuação não encontra alternativa.

O tempo das raízes é a **ordem de todas as ocorrências**, não segundos de relógio.
Capturas (`stream_id`) separam histórias temporais automaticamente a partir
da origem. Não criam uma associação semântica. O primeiro testemunho de cada
par `(origem, destino)` por hierarquia fixa seu voto e peso; novos testemunhos
desse mesmo par não somam suporte. Uma ocorrência repetida pode, porém,
aproximar ou afastar pares **ainda inéditos** na mesma captura. O campo de
símbolos e os suportes de continuação continuam derivados das entradas de
conteúdo único. A projeção de nódulos intermediários usa conteúdo único para
definir padrões e relações dentro de cada payload, mas todas as ocorrências
para formar pares temporais inéditos entre payloads. Ela reconstrói os campos
a partir da ordem preservada, sem alterar os nódulos armazenados;
ela ainda não substitui a evocação entre raízes quando a consulta é um
payload completo já conhecido.

### Nódulos intermediários, sem vínculos manuais

Ao encontrar uma sequência recorrente em dois payloads **diferentes**, o
experimento projeta suas ocorrências sobre os símbolos originais, inclusive
nas entradas anteriores à descoberta. A projeção inclui todas as posições
exatas, mesmo as que uma compactação gulosa teria escondido. Nenhuma entrada
histórica é regravada. Padrões recorrentes de 2 até 32 símbolos podem se
tornar candidatos derivados, mantendo a formação hierárquica existente para
os níveis posteriores. O limite usa `max_context` e pode ser configurado.

Cada ocorrência mantém o intervalo `[início, fim)` dentro do payload.
Composições sobrepostas não geram relação direcional de proximidade espacial.
Entre entradas de uma mesma captura, o peso temporal preserva a ordem e o
decaimento por distância entre **todas** as ocorrências. O primeiro testemunho
de cada par de payloads distintos contribui uma vez, também quando uma das
pontas reutiliza conteúdo conhecido. Repetições posteriores desse mesmo par
preservam a posição e a proveniência para traçar caminhos, sem reforçar peso.
As relações internas ainda usam cada payload distinto uma vez. Origens
`(payload anterior, payload posterior, captura)` acompanham os votos; um
caminho de dois saltos exige também a **mesma ocorrência intermediária** na
mesma captura. Essas origens são estruturais, não votos de verdade.

`associated_nodules` procura primeiro o trecho recorrente mais longo contido
na consulta **que tenha um destino associado**. Se o trecho maior não tiver
saída, recua para o próximo comprimento; não transforma a ausência de relação
num bloqueio das rotas menores. Consulta todas as escalas que representam o
mesmo trecho e reúne os alvos distintos. Um alvo já contido na própria
consulta não vira outra evocação dela mesma. Uma representação repetida do
mesmo alvo em outra escala não soma um novo voto; o campo `depth` informa a
escala mais profunda do trecho usado. Exibe canal, escala, peso e origens.
Com `include_shorter=True`, a consulta também reúne destinos testemunhados por
trechos recorrentes mais curtos, mesmo se o trecho maior tiver uma saída. Um
destino comum fica uma vez, com o peso da pista mais longa e a união das
testemunhas; fragmentos de alvo com as mesmas testemunhas e sem maior peso
cedem à versão que os contém. A pista mais longa aparece primeiro e o limite
marca `truncated` se outras alternativas ficarem de fora. A leitura comum
mantém `include_shorter=False` para não inundar os diagnósticos e as medidas
de estabilidade com fragmentos ocasionais. `source_width` identifica o
comprimento da pista primária; os escores de geração são normalizados apenas
entre destinos desse mesmo comprimento.
Nódulos curtos
contidos em outro com **as mesmas origens** deixam de disputar com a versão
maior; os que têm origens distintas permanecem. Para ordenar alternativas,
usa `peso × comprimento do alvo`: um prior de especificidade não calibrado.
O peso bruto permanece acessível e nem o escore nem a posição certificam
verdade. Só há `selected` quando resta uma única alternativa sem truncamento.
Pesos brutos de escalas diferentes têm normalizações distintas; a ordem entre
alvos de comprimentos e escalas diferentes ainda precisa de calibração.

`generate` usa essa evocação (`NODULE_RECALL`) quando não encontra outra
família de rota. Se houver continuação ou evocação de raiz simultânea, mantém
as alternativas juntas. O nódulo evocado é mostrado separadamente; não se
afirma que a frase toda tenha sido observada. Se a leitura comum apresentar
uma **única** rota de nódulo sem truncamento, `generate` consulta também as
pistas menores: uma saída diferente ou um limite atingido impede `selected`.
Consultas já ambíguas mantêm a leitura comum; a expansão completa pode ser
inspecionada à parte. A prioridade entre comprimentos não é uma probabilidade.

Um payload completo conhecido já é uma raiz reutilizável mesmo que só tenha
aparecido uma vez. Se uma consulta inédita contém essa sequência inteira,
`embedded_root_relations` procura as raízes contidas mais longas **com uma
entrada posterior na mesma captura**. Se as raízes maiores não tiverem
sucessor, recua para o próximo comprimento. Raízes sem ligação não consomem
o limite de candidatos nem diluem o peso de outras raízes do mesmo tamanho.
Mesmo que uma raiz maior tenha sucessor, as raízes menores contidas também
preservam suas próprias ligações. Os destinos da raiz maior aparecem primeiro;
pesos só são comparados entre raízes do mesmo comprimento. Um destino que
aparece em mais de uma escala é listado uma vez, com o peso da escala mais
específica e as testemunhas de ambas nas ligações. O limite descarta primeiro
as raízes menores e marca truncamento, sem permitir seleção única. O parâmetro
`include_shorter=False` reproduz a leitura anterior de uma só escala para
comparação diagnóstica. O escore de geração da raiz embutida é normalizado
somente dentro do comprimento de origem; não representa probabilidade entre
comprimentos diferentes.
`EMBEDDED_TEMPORAL_RECALL` expõe a raiz de origem, cada raiz de destino, peso
e capturas testemunhas quando não há outra família de candidatos. Uma consulta
que coincide com a raiz completa pode evocar suas entradas posteriores por
`TEMPORAL_RECALL`. Quando mais de uma família encontra candidatos,
`COMBINED_RECALL` expõe todas as evidências e une os destinos distintos sem
somar seus pesos. A raiz exata vem primeiro, seguida pela raiz embutida e pelos
nódulos recorrentes. Se uma continuação também existe, o modo é
`COMBINED_ROUTES`: as ramificações de continuação aparecem primeiro, inclusive
o término observado concorrente, seguidas pelas evocações. Se o limite da
busca descartar uma continuação e restar somente o término observado, a rota
evocada ainda aparece como evidência; o resultado permanece truncado e sem
seleção. Os passos da
continuação e as testemunhas das evocações permanecem inspecionáveis; os
escores continuam relativos **dentro de cada família** e não são comparáveis
entre elas. Um destino coincidente é mostrado uma vez; destinos diferentes
mantêm ambiguidade.
Duas raízes ou dois destinos concorrentes também mantêm
`ambiguous`; limite de busca mantém `truncated` e impede `selected`. O modo
também cobre uma nova consulta que termina exatamente com a raiz conhecida.
Não usa `reply_to` e não converte proximidade temporal em fato: o sucessor
pode ser uma distração. A prioridade por comprimento é uma ordem de exibição,
sem calibração de pesos entre escalas. Se a união exceder o limite
de candidatos, as evidências efetivamente coletadas continuam inspecionáveis e
o resultado marca truncamento. O cálculo hoje ocorre durante a consulta. Organizá-lo em
segundo plano continua sendo uma etapa futura.

Na [prova cronológica](trajectory-episode-proof.md#prova-cronológica-de-evocação),
duas capturas com pistas em contextos diferentes tornam um alvo evocável antes
de observar a terceira captura. Uma entrada intermediária nova, logo após a
terceira pista, ativa a raiz exata: anteriormente ela substituía o alvo antigo
por essa entrada recente como única saída estrutural. Agora ambos aparecem,
com suas capturas testemunhas, e `selected` fica vazio. O caso não informa à
memória qual deles é resposta verdadeira. Outro controle aprende uma
continuação em um contexto separado depois das duas primeiras capturas: a
consulta inédita agora mostra tanto a continuação quanto o destino recorrente.
São 24 variações com endereços opacos em duas sementes do gate online. Cópias
em capturas separadas que não criam pares novos não alteram os resultados;
reabertura reproduz a saída e limite curto
marca truncamento sem selecionar uma resposta. Isso prova a preservação de
evidências no experimento; não prova qual rota é verdadeira.

O mesmo gate observa um destino armazenado primeiro numa captura antiga e
depois de uma pista nova em outra captura. Antes da segunda ocorrência, a
consulta que contém a pista devolve eco; depois, evoca o destino por uma
ligação raiz embutida → destino. O conteúdo continua único. Repetir esse
mesmo par em outra captura não soma peso; inverter a ordem não cria ligação
na direção da pista para o destino. Isso passou nas 24 variações.

## Escalas e inferência

O índice ganha uma opção `preserve_repetitions=True`, usada pelo experimento.
O padrão histórico, que colapsa repetições imediatas, é preservado para os
consumidores anteriores.

O motor hierárquico encontra sequências recorrentes em pelo menos dois
payloads distintos. Seus endereços podem formar novas sequências e níveis.
O mesmo mecanismo de continuação opera sobre símbolos e composições:

- Procura o maior sufixo conhecido do contexto atual.
- Encontra os próximos endereços e o término observado, com testemunhas por
  payload. Correspondências podem atravessar o interior de um nódulo maior;
  empacotar um trecho não deve ocultar seus prefixos e sufixos.
- Mantém ramificações, acumula suporte e repete o processo.
- Pode combinar passos de ocorrências diferentes. Cada passo identifica suas
  testemunhas; a trajetória completa resultante é uma hipótese gerada.
- Se houver relação temporal da raiz consultada, evoca payloads posteriores
  na mesma captura, mesmo quando existe continuação.
- Sem alternativas, devolve a entrada (`ECHO`).

A escolha automática de escala prefere a maior extensão atômica do contexto
encontrado e, em empate, o nível mais profundo. É possível fixar uma escala
para comparar o comportamento. Composições podem avançar vários símbolos de
uma vez; os escores entre escalas não são probabilidades calibradas.

Concorrentes continuam disponíveis mesmo quando um tem mais suporte. O campo
`selected` só existe para uma hipótese única, sem ambiguidade nem truncamento.
Um escore alto não determina verdade. `ECHO`, `CONTINUATION`,
`TEMPORAL_RECALL`, `NODULE_RECALL`, `EMBEDDED_TEMPORAL_RECALL` e
`COMBINED_RECALL` ou `COMBINED_ROUTES` descrevem a operação realizada.

Limites iniciais, configuráveis:

- contexto mínimo de 2 endereços, ou a consulta inteira se tiver apenas 1;
  evita continuar uma frase nova por um único caractere acidental;
- até 32 endereços de contexto por escala;
- até 3 níveis de composição, trechos de 2 a 3 filhos, catálogo máximo de
  2.048 composições por nível;
- até 32 passos e 8 hipóteses na busca;
- campo contínuo omite contribuições inferiores à precisão de `1e-6`.

A busca informa limites de passos e descarte de hipóteses com `truncated`.
Não transforma um desempate por endereço em resposta confirmada. Ainda pode
produzir continuações sem sentido por coincidência estrutural. Quando a leitura
principal já é ambígua, a geração conserva os destinos do trecho maior. Se
parecer única, verifica também pistas menores e suspende a seleção diante de
outra rota ou truncamento; comparar pesos entre comprimentos ainda exige
calibração. A busca de continuações também pode cortar rotas;
as testemunhas de uma evocação independente continuam inspecionáveis, mas
não recuperam a ramificação descartada.

## Reuso da projeção de leitura

Sem nova ocorrência, consultas sucessivas reutilizam a projeção derivada da
última hierarquia ativa. Uma ocorrência com ID novo invalida essa projeção,
inclusive quando reutiliza conteúdo; reexecução do mesmo ID não altera o
cache nem o aprendizado. O cache não é persistido. A prova de paridade e seus
limites estão em [trajectory-projection-reuse-proof.md](trajectory-projection-reuse-proof.md).

## Evidência do gate

Primeira etapa em 27/09/2026: 22 testes novos e 64 regressões passaram no
workflow; um teste do backend BDR opcional foi pulado. Nesta etapa de
associação intermediária, 33 testes do experimento passam localmente, com
dois novos testes do campo posicional. O workflow também verifica os
consumidores anteriores do índice e o índice persistente.

Os testes cobrem bootstrap com `oi`, `hoje o dia está bonito` e `hoje está
quente`; reuso sem reforço; inclusão de um nódulo em outro payload; formação
de múltiplas escalas; preservação de competidores dentro de nódulos maiores;
continuação de contexto inédito; combinação de trajetórias de entradas
diferentes; fim concorrente; limites de ciclos e ramificações; ordem e
isolamento temporal; isolamento de hierarquias; renomeação de símbolos;
bytes/Unicode sem perda; nenhuma autoalimentação; rejeição de identidade
alterada e estado corrompido; persistência SQLite com reabertura idêntica.
Os novos controles incluem: nódulo interno descoberto retrospectivamente;
associação automática entre entradas próximas; redução de peso por um evento
interposto; inversão temporal; capturas separadas; trechos sobrepostos que
não produzem aresta falsa; reaparecimento em contexto distinto versus cópias;
composição longa em outra escala; renomeação opaca; e reabertura idêntica.

Exemplo controlado: `(1, 2, 3)` recorrente em contextos diferentes precede
`(7, 8, 9)` também recorrente. Uma consulta inédita contendo `(1, 2, 3)`
evoca `(7, 8, 9)` com três pares de entradas testemunhando a relação. Na
demonstração com caracteres Unicode, `quarto` pode ativar o trecho recorrente
`a cama ` como **primeira hipótese**, mas outras combinações curtas competem,
portanto a saída não é declarada única nem uma afirmação sobre o mundo.

Exemplo: depois de observar `hoje o dia está bonito`, a consulta
`amanhã o dia está ` gera `amanhã o dia está bonito`. A frase completa gerada
não estava armazenada. Isso demonstra recombinação estrutural simples.

**Ainda não demonstra** compreensão de linguagem, equivalência a LLM,
cognição humana, aprendizado perceptivo de áudio/imagem ou generalização
robusta em conversas reais. O mecanismo é próximo de um modelo de contexto
variável com composições e evocação associativa. Testes sintéticos demonstram
os contratos programados. A primeira [avaliação com contextos reservados](trajectory-holdout-proof.md)
mede generalização estrutural e controles negativos em dois lotes pequenos;
a [reprodução agregada de um export do OFF.IA](trajectory-offia-replay.md) mede
um vínculo observado entre entradas reais. Mais conversas e modalidades não
textuais ainda exigem provas próprias.

Uma [prova entre conversas sintéticas](trajectory-episode-proof.md) também
verifica rotas concorrentes, testemunhas por captura e ambiguidade após
distração sem vínculos manuais. `trace_nodule_paths` pode encadear até dois
saltos quando o alvo do primeiro e a origem do segundo são a **mesma ocorrência
do mesmo payload na mesma captura**. Expõe as sequências de IDs que testemunham cada
caminho, sem escolher resposta factual nem juntar duas conversas por terem um
nódulo parecido. O limite de candidatos por salto e o truncamento ficam
visíveis. O armazenamento SQLite foi exercitado neste
gate; BDR e integração nativa
precisam de validação própria. Otimização, organização em segundo plano e
integração ao ciclo de respostas do aplicativo são etapas posteriores.

A [prova de estabilidade estrutural](trajectory-stability-proof.md) separa
peso, participação relativa, pares testemunhas e capturas independentes. Ela
mostra que contextos diferentes acumulam evidência, uma ocorrência isolada
não forma rota recorrente e cópias exatas não reforçam. Uma liderança de peso
continua sendo diagnóstico; candidatos concorrentes mantêm `selected` vazio.
