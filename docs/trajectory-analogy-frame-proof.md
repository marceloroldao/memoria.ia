# Analogia estrutural entre pares observados e raízes isoladas

## Experimento separado

Novo diagnóstico somente leitura `trajectory_analogy_frame_probe.py`. Não altera a geração, a hipótese opcional anterior, o runtime ou OFF.IA. Ele testa se uma relação aprendida em pares de outros sujeitos permite encontrar um payload inteiro já armazenado em uma captura isolada.

Acrescentar exemplos muda as condições do experimento: **não transforma o resultado anterior 26/32 em 32/32**. A ponte anterior e seus seis critérios pendentes permanecem preservados. Este diagnóstico utiliza outra bateria, com estágios de treinamento explícitos e todos os rótulos exclusivamente no avaliador.

## Mecanismo

Três pares adjacentes distintos, derivados da ordem real de observações na mesma captura/segmento, precisam compartilhar prefixo e sufixo na origem. Os três trechos variáveis de origem precisam ser distintos, não vazios e aparecer exatamente uma vez no respectivo destino. O trecho anterior à variável nos destinos deve ser idêntico e não vazio. Após a variável copiada, exige prefixo e sufixo comuns não vazios, delimitando três valores distintos e não vazios.

O padrão aprendido tem uma variável na origem e uma variável copiada mais um valor livre no destino. A consulta precisa corresponder à moldura completa da origem, admitindo prefixo inédito, mas apenas uma ocorrência da pista de prefixo. Com o trecho variável extraído, a leitura procura **raízes inteiras já observadas** que correspondam à moldura de destino. Retorna todos os IDs encontrados, testemunhas dos três pares e IDs dos padrões. Um único payload vira hipótese estrutural; vários mantêm abstenção. Nenhuma nova frase é composta ou gravada.

O número três é um requisito conservador deste diagnóstico; não uma lei arquitetural. Não há classificação de nomes, sujeitos, fatos, perguntas ou cores. Prefixos/sufixos são sequências brutas aprendidas dos exemplos. Exemplos concretos e rótulos esperados estão no fixture, não no seletor. Unicode, UTF-8, renomeação bijetiva e um teste inteiramente numérico verificam o mesmo mecanismo.

## Bateria e resultados locais

As informações de drone/robô ficam nas capturas isoladas originais. Os exemplos pareados usam barco/avião/sensor e valores diferentes. A saída fictícia do assistente permanece excluída. Há sete consultas por estágio: pergunta conhecida, prefixo novo, outro sujeito, relação alterada, sujeito ausente, consulta desconexa e duas pistas completas na mesma consulta. Cada estágio usa dois adaptadores e renomeação, quatro versões correlacionadas.

| Estágio | Critérios | Resultado |
|---|---:|---|
| Sem exemplos pareados | 16/28 | FAIL; três perguntas esperadas continuam sem resposta em cada versão |
| Três pares observados | 28/28 | PASS; informações isoladas recuperadas |
| Destino isolado conflitante | 28/28 | PASS; ambas as raízes preservadas, sem hipótese única |
| Exemplo interrompido por assistente | 16/28 | FAIL; apenas dois pares válidos, sem padrão aprendido |
| Relações concorrentes aprendidas | 28/28 | PASS; candidatos de ambas as relações preservados |
| Total | 116/140 | **FAIL** |

Respostas corretas 20/44; consultas de ausência retornam zero candidatos em 80/80; conflitos preservados 16/16; zero hipóteses diferentes do alvo esperado. Nos três estágios com treinamento suficiente, 84/84 critérios passam. Os 24 critérios restantes continuam falhando: não contamos abstenção sem treinamento como resposta correta. Os exemplos foram escolhidos para este primeiro diagnóstico, sem lote independente de conversas reais.

Na concorrência de relações, os mesmos formatos de origem têm três exemplos com destino de nome e três com destino de cor. A consulta preserva as raízes de nome/cor do drone e se abstém. A composição também produz molduras mais amplas; todas permanecem visíveis. Isso mostra a ambiguidade, não descobre uma classificação factual ou preferência entre relações.

## Integridade e limites

Seis testes verificam necessidade dos exemplos, relação alterada/ausência, sequências opacas, renomeação, repetição sem diversidade, barreira do assistente, destinos/relações concorrentes, separação de captura e rejeição de variável copiada mais de uma vez. Os seis testes novos e 59 do gerador passaram localmente. Cada leitura compara geração completa, estado de aprendizado, snapshot e resultado após restauração. Consultas e respostas geradas não são observadas como treinamento.

`--library <libmemoria_mobile.so>` observa os fixtures via ABI, lê janelas, reabre o BDR e alimenta o diagnóstico com as janelas frias. Confere igualdade completa com a avaliação dos registros de entrada. O relatório inclui o mapa de todos os IDs de raiz para endereços nativos, inclusive após renomeação. `--strict-quality` foi executado localmente e retorna 1 para FAIL 116/140.

O seletor não está integrado ao motor. A busca combina trios de pares e varre raízes; o custo cresce com os dados, sem promessa de escalabilidade. Só cobre a moldura contígua estreita descrita acima. Variações internas, cópias múltiplas, relações com vários campos, generalizações espúrias e diversidade de domínios permanecem por testar. Nenhuma equivalência a linguagem geral, inteligência humana ou verdade factual é demonstrada.

PR draft, sem ativação no OFF.IA. O gate nativo original segue com três falhas pendentes.

## Validação concluída

[Workflow 36896990596](https://github.com/marceloroldao/memoria.ia/actions/runs/36896990596) passou no commit `7c7127cf9882d543b218950978cdcc776087e477`: seis testes novos no job nativo, 59 do gerador, 18 da hipótese padrão, oito da opção anterior e 66 regressões (um BDR opcional pulado), além dos controles anteriores. Todos os outros workflows aplicáveis passaram; experimental PR regression foi pulado pela condição existente.

O job compilou o runtime inalterado com BDR fixado, observou as cinco configurações e confirmou janelas iguais após reabertura. O diagnóstico foi alimentado pelas janelas frias. O relatório completo coincide exatamente com a pré-verificação local em todos os campos comuns, incluindo padrões, candidatos, hipóteses, testemunhas e mapa de proveniência; apenas os indicadores de execução nativa/reabertura diferem. Resultado **FAIL 116/140**, ausência vazia 80/80, conflitos 16/16 e zero hipóteses diferentes do alvo esperado. Nos três estágios com treinamento suficiente, 84/84 critérios passaram. Esses números vêm de versões correlacionadas dos mesmos sete desafios por estágio.

Relatório completo dos logs salvo em `benchmark-results/trajectory-analogy-frame-report.json`. A comparação anterior foi executada no mesmo job e manteve a opção experimental FAIL 26/32. Os cinco lotes padrão de variações continuam PASS 150/150. Sucesso do workflow indica integridade/reprodução, não aprovação da qualidade geral nem integração da analogia ao motor.

Próxima pendência: diversidade de formas e campos, controles adversariais de generalização e custo de descoberta antes de considerar integração. Os casos sem treinamento e com barreira continuam como falhas no scorecard.
