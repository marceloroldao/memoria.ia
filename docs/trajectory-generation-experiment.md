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
cópias em outra ocorrência ou outra captura não aumentam pesos, suporte,
relógio de aprendizado ou número de trajetórias. Uma hierarquia nova aprende
separadamente, compartilhando a tabela de conteúdo armazenado.

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
| Entradas novas separadas por k eventos na mesma captura | `exp(-0.35 * (k - 1))` | Campo temporal e evocação de payloads |
| Símbolos entre entradas | Kernel temporal multiplicado pelas frequências normalizadas dos símbolos em cada entrada | Associação temporal inspecionável |
| Esquecimento | Desativado por padrão (`forgetting_rate=0`) | Configurável, ainda sem calibração empírica |

O suporte de continuação conta no máximo um voto por payload e próximo
endereço; um payload pode testemunhar opções diferentes em posições distintas.
O campo de distância registra ocorrências posicionais, preservando inclusive
autorrelações. São medidas diferentes e são expostas separadamente.

Os parâmetros são hipóteses de engenharia, não pesos aprendidos por gradiente
ou valores biologicamente validados. Os pesos de distância entre símbolos
ainda não são combinados com o escore de continuação. O campo de raízes fornece
evocação temporal quando a continuação não encontra alternativa.

O tempo usado aqui é a **ordem das entradas novas**, não segundos de relógio.
Capturas (`stream_id`) separam histórias temporais automaticamente a partir
da origem. Não criam uma associação semântica. Cópias excluídas do aprendizado
também não consomem posições temporais: é uma escolha explícita desta versão.
Como cada raiz contribui uma vez por hierarquia, a evocação temporal entre
raízes ainda não acumula repetidas ocorrências do mesmo par. A recorrência
entre contextos diferentes já aparece no campo de símbolos e nos suportes
das continuações. A nova projeção de nódulos intermediários recupera relações
entre composições, reconstruindo os campos a partir das entradas únicas;
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
decaimento por distância entre eventos. Payload repetido não avança o relógio
de aprendizado. Origens `(payload anterior, payload posterior, captura)`
acompanham as relações encontradas; relações internas usam o mesmo payload
nas duas pontas. Essas origens são estruturais, não votos de verdade.

`associated_nodules` retorna os nódulos ligados ao trecho recorrente mais
longo contido na consulta. Consulta todas as escalas que representam esse
mesmo trecho e reúne os alvos distintos. Uma representação repetida do mesmo
alvo em outra escala não soma um novo voto; o campo `depth` informa a escala
mais profunda consultada. Exibe canal, escala, peso e origens. Nódulos curtos
contidos em outro com **as mesmas origens** deixam de disputar com a versão
maior; os que têm origens distintas permanecem. Para ordenar alternativas,
usa `peso × comprimento do alvo`: um prior de especificidade não calibrado.
O peso bruto permanece acessível e nem o escore nem a posição certificam
verdade. Só há `selected` quando resta uma única alternativa sem truncamento.
Pesos brutos de escalas diferentes têm normalizações distintas; a ordem entre
alvos de comprimentos e escalas diferentes ainda precisa de calibração.

`generate` usa essa evocação (`NODULE_RECALL`) como última opção quando não
encontra continuação nem evocação da raiz e a rota terminou por falta de
evidência. O nódulo evocado é mostrado separadamente; não se afirma que a
frase toda tenha sido observada. O cálculo hoje ocorre durante a consulta.
Organizá-lo em segundo plano continua sendo uma etapa futura.

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
- Se faltar continuação e houver relação temporal da raiz consultada, evoca
  payloads posteriores na mesma captura.
- Sem alternativas, devolve a entrada (`ECHO`).

A escolha automática de escala prefere a maior extensão atômica do contexto
encontrado e, em empate, o nível mais profundo. É possível fixar uma escala
para comparar o comportamento. Composições podem avançar vários símbolos de
uma vez; os escores entre escalas não são probabilidades calibradas.

Concorrentes continuam disponíveis mesmo quando um tem mais suporte. O campo
`selected` só existe para uma hipótese única, sem ambiguidade nem truncamento.
Um escore alto não determina verdade. `ECHO`, `CONTINUATION`,
`TEMPORAL_RECALL` e `NODULE_RECALL` descrevem a operação realizada.

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
produzir continuações sem sentido por coincidência estrutural.

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
conversas reais e modalidades não textuais ainda exigem provas próprias.

O armazenamento SQLite foi exercitado neste gate; BDR e integração nativa
precisam de validação própria. Otimização, organização em segundo plano e
integração ao ciclo de respostas do aplicativo são etapas posteriores.
