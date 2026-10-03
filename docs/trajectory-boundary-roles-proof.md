# Concordância completa e papéis não observados

A concordância entre cortes estabelece compatibilidade com raízes observadas. Este experimento testa se ela também identifica uma intenção de resposta que não foi codificada. O leitor e o resumo anteriores permanecem inalterados; dois motores independentes recebem exatamente os mesmos símbolos, endereços de ocorrência, capturas, hierarquias e ordem. Somente o avaliador conhece os dois contratos abaixo.

| Contrato do avaliador | Resposta esperada | Dados entregues ao motor |
| --- | --- | --- |
| Destino pretendido como resposta | Raiz reservada completa | Mesmas observações e mesma consulta |
| Destino como outro evento adjacente | Abstenção | Mesmas observações e mesma consulta |

Os papéis não entram em `observe`, na consulta, na restauração nem nos leitores. Não há marcador de fala, interlocutor, intenção ou validade factual no fluxo. O primeiro contrato é uma expectativa do teste, não uma prova de verdade do conteúdo. O segundo não afirma que o conteúdo observado seja falso: exige não usá-lo como resposta ao evento anterior. As expectativas permanecem fixas mesmo depois de introduzida uma raiz rival; não se elimina o positivo difícil para elevar o resultado.

## Sequência de intervenções

Reutiliza o controle de cópias contíguas no destino: cada corte da consulta concatena o mesmo corpo, e a raiz reservada sustenta todos os cortes de cada quadro. É equivalência de concatenação, não confirmação independente por cada corte.

| Estágio | Raízes de continuação exata | Ocorrências de continuação | Raízes nos cortes | Unanimidade por quadro |
| --- | --- | --- | --- | --- |
| Concordância inicial | 0 | 0 | 1 | Sim |
| Duas repetições isoladas da raiz | 0 | 0 | 1 | Sim |
| Consulta isolada | 0 | 0 | 1 | Sim |
| Consulta seguida da raiz reservada | 1 | 1 | 1 | Sim |
| Nova ocorrência da mesma sequência | 1 | 2 | 1 | Sim |
| Consulta seguida da raiz rival | 2 | 3 | 2 | Não |

Em cada estágio, os snapshots e os pacotes completos dos dois motores são iguais. A igualdade é conferida diretamente antes de registrar os fingerprints SHA-256. Cada leitura também verifica restauração fria, ausência de mutação, aprendizado e geração padrão inalterados, raízes endereçadas e testemunhas posicionais. O relatório guarda um pacote completo por estágio, compartilhado apenas na apresentação após a igualdade ser verificada; os motores e suas leituras são independentes. Conserva proveniência e as duas expectativas contraditórias.

As repetições isoladas e a consulta sem sucessor não alteram o pacote. A repetição da sequência exata acrescenta uma testemunha endereçada, mantendo a mesma raiz e o mesmo diagnóstico de concordância. A enumeração atual produz mais quadros testemunhados: 27 inicialmente, 108 após a primeira continuação, 189 após sua repetição e 378 após a rival. Esses números incluem combinações de cortes e testemunhas; não contam evidências semanticamente independentes e não são votos. O experimento registra esse crescimento sem otimizar ou alterar o leitor.

## Resultado e contraexemplo de autorização

Cada lote (20261117 desenvolvimento, 20261118 reservado) executa seis estágios, com duas versões por bijeção. São **12/12 controles de integridade**, mas **24 avaliações de resposta**, pois cada estágio tem os dois contratos do avaliador.

| Política avaliada | Positivos respondidos corretamente | Abstenções corretas | Respostas indevidas | Total correto |
| --- | --- | --- | --- | --- |
| Leitor atual, sem autorização | 0/12 | 12/12 | 0 | **12/24 FAIL** |
| Comparador do avaliador que força consenso único | 10/12 | 2/12 | 10 | **12/24 FAIL** |

O comparador só existe no avaliador: propõe a raiz quando todos os quadros concordam com uma única raiz, e suspende quando surge a rival. Não foi instalado no leitor, motor ou OFF.IA. Seus dez acertos positivos correspondem a dez respostas indevidas no contrato gêmeo. A abstenção atual evita essas respostas, mas mantém os doze positivos como falhas. Portanto, não se reivindica uma solução funcional por suspender tudo.

Para uma função determinística que recebe apenas observações e consulta iguais, a saída também será igual. Como as duas expectativas são diferentes, ela não pode satisfazer ambos os contratos deste par. Repetir o mesmo fluxo não revela o papel que permaneceu fora dele. Esse limite vale para o par construído, não é uma impossibilidade de aprender intenção quando ela se manifesta em observações adicionais, nem uma comparação de capacidade com LLMs.

São controles correlacionados, com expectativas impostas pelo avaliador para expor subdeterminação. Os 24 casos não são uma taxa geral de compreensão. A bateria estrutural anterior continua **98/126 FAIL**, registrada separadamente com `recomputed:false`; os testes anteriores a recalculam. Resultados e denominadores históricos permanecem preservados.

## Reprodução e próxima direção

Seis testes novos verificam resultados positivos ainda falhando, igualdade dos motores sob concordância completa, endereços das continuações e ausência de papéis no fluxo, repetição/rival sem autorização, isolamento do comparador e invariância por bijeção. Relatórios completos: `benchmark-results/trajectory-boundary-roles-{development,reserved}.json`. Reprodução: `python scripts/trajectory_boundary_roles_probe.py --seed 20261117` ou `--seed 20261118`. O comando comum verifica integridade; `--strict-quality` retorna 1, explicitando o FAIL de resposta. A CI executa testes e ambos os lotes sem converter sucesso de integridade em aprovação semântica.

Runtime nativo, seletores anteriores, OFF.IA e gaps dos gates pessoais permanecem inalterados. Próxima direção: testar contexto adicional efetivamente observado e transportado entre origem e destino, com controles cruzados que separem resposta de outro evento. A distinção precisa aparecer no fluxo; não pode vir apenas do nome do caso, de uma etiqueta do avaliador ou da quantidade de quadros que repetem a mesma informação.

Validação local: **210 testes passaram, um teste opcional de BDR foi pulado**, incluindo os seis novos testes, os probes anteriores e os consumidores estruturais. Os dois lotes reproduziram os mesmos agregados; o modo estrito foi confirmado retornando 1, com integridade PASS e qualidade de resposta FAIL. `git diff --check` passou.

O contexto adicional observado foi investigado em [Contexto observado e discriminação de raízes](trajectory-observed-context-proof.md). O transporte discrimina destinos com códigos de contexto distintos, mantendo a autorização semântica suspensa e as falhas deste diagnóstico de gêmeos.
