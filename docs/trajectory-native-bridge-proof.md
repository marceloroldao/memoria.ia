# Ponte de diagnóstico BDR nativo / trajetórias, 30/09/2026

## Escopo

Nova comparação somente leitura, sem ativar a inferência no runtime ou OFF.IA:

`python scripts/trajectory_native_bridge_probe.py --library build/trajectory-native/libmemoria_mobile.so`

O workflow compila a biblioteca nativa inalterada com o BDR fixado em
`317882a00f041fc1568ff986af8016b09453f21a`, executa o gate pessoal original e
este probe. Os cenários são fictícios. Não há argumento para export privado,
nem consulta externa ou LLM. O sucesso do workflow verifica integridade; a
qualidade completa continua separada, com `--strict-quality` disponível.

O objetivo é verificar se o resultado da bateria de códigos fictícios se transfere
para as entradas do diagnóstico pessoal, usando as mesmas observações. Um PASS
150/150 no teste anterior não implica resolver os três gates pessoais nativos.

## Caminho do teste

1. Observa as entradas fictícias pela ABI nativa em um diretório BDR temporário.
2. Lê janelas endereçáveis por captura e compara texto, papel, ID e sequência com
   as entradas fornecidas. A ordem global de observação do fixture é preservada.
3. Fecha/reabre o runtime e compara as janelas e a resolução pessoal completas.
4. Constrói a memória Python somente com registros lidos das janelas reabertas,
   em símbolos Unicode ou bytes UTF-8 brutos, sem normalização de caixa/palavras.
5. Verifica leitura sem aprendizado, reconstrução fria Python e endereçamento
   de todas as testemunhas de continuação, raiz exata, raiz embutida e nódulos.

Capturas diferentes não criam relações temporais. `assistant_generated` não
entra na memória e incrementa o segmento da captura: não é permitido remover
o turno do assistente e unir a pergunta à resposta do usuário que veio depois.
`user_assertion` é um papel observado, não um rótulo que transforme pergunta em fato.
O mapa de raízes mantém todos os endereços de origem de conteúdo reutilizado.
Nenhum `reply_to` manual ou resposta esperada entra no aprendizado.

## Cenários e resultados

| Cenário | Situação | Critérios confirmados no CI |
| --- | --- | --- |
| legacy_isolated | Os dez registros iniciais do gate pessoal, sem relações ordenadas pergunta/resposta entre capturas | 2/8, FAIL |
| ordered_pairs | Pergunta/resposta observadas na mesma captura para drone e robô | 2/8, FAIL |
| ordered_conflict | Acrescenta outra resposta observada para a pergunta do drone | 6/8, FAIL |
| assistant_barrier | Pergunta, saída gerada, usuário posterior; par independente para robô | 8/8, PASS |

São quatro consultas em dois adaptadores por cenário: conhecida, prefixo novo,
outro sujeito e recombinação ausente. Os adaptadores do mesmo texto não são casos
independentes. A pré-verificação local deu 18/32 critérios, 2/16 respostas corretas e zero
hipóteses indevidas. A execução da ABI/BDR confirmou os mesmos resultados. Os
32 casos completos do adaptador local coincidem exatamente com a comparação
alimentada pelas janelas nativas reabertas; a integridade passa, a qualidade falha.

Na memória isolada, a inferência dá eco sem hipótese; não existe par temporal
para aprender a resposta de uma pergunta armazenada em outra captura. Nos pares
ordenados, as respostas completas são retidas, mas fragmentos de destinos distintos
ativados pelos trechos compartilhados impedem consolidação. No cenário de conflito,
ambas as respostas ficam visíveis e sem escolha única, mas a pergunta do robô
também fica sem hipótese. O caso de barreira não transforma a saída gerada em
conhecimento nem pula até a resposta posterior do usuário.

Esta nova evidência amplia a limitação: a proteção de escopo anterior não basta
para separar todas as rotas de frases descritivas diferentes. Os critérios não
foram retirados nem as abstenções contadas como respostas corretas. A próxima
correção precisa tratar a sustentação de fragmentos entre destinos distintos e
conservar os controles que recusam conflitos realmente ligados à pista completa.

## Contratos locais e limites

Cinco testes do adaptador passaram: preservar caixa/acentos/conteúdo reutilizado;
barreira de assistente; isolamento entre capturas; rejeitar endereço/sequência
duplicado, invertido ou empatado e papel desconhecido; pergunta marcada como
asserção continua sem resposta por simples marcação. Runtime, inferência,
snapshots e endpoints nativos não foram alterados.

A biblioteca nativa não está disponível neste ambiente local; compilação,
reabertura BDR e reprodução do gate original são verificadas no novo job de CI.
O relatório emitido contém contagens, motivos, hipóteses fictícias e condições de
endereço, sem export pessoal. O diagnóstico nativo permanece não qualificado.
OFF.IA continua sem a política; o PR permanece draft e os três gates nativos
originais não são declarados resolvidos.

## Confirmação remota

O [workflow 36800155214](https://github.com/marceloroldao/memoria.ia/actions/runs/36800155214)
passou no commit `a6561e721181b92f709e4448e1544b0311f569c6`. O job native-bridge
passou nos cinco testes do adaptador, compilou a biblioteca com BDR fixado,
executou o gate pessoal original e verificou a ponte após reabrir BDR. Gate
original: 23/26, com FAIL em known_answer_first, other_subject_first e
absent_recombination_empty. Nos registros isolados, os primeiros candidatos
continuam near-echo, echo-1 e motor-power, respectivamente, sempre sem qualificação.

A nova comparação confirma FAIL 18/32, respostas 2/16, ausência 12/12,
conflitos 4/4 e zero hipóteses indevidas. Todas as janelas e resoluções nativas
ficaram iguais após reabertura; todas as testemunhas Python foram endereçáveis.
O job proof preservou os cinco lotes anteriores PASS 150/150 e passou em
18 testes da hipótese, 59 do gerador e 66 regressões (1 BDR opcional pulado).
Os outros workflows aplicáveis também passaram.

Relatórios fictícios completos extraídos dos logs, sem export pessoal:
`benchmark-results/trajectory-native-bridge-report.json` e
`benchmark-results/trajectory-native-bridge-reference.json`.
O primeiro registra a ponte e todos os casos; o segundo registra o gate nativo
original. Sucesso do CI não aprova os gates de qualidade que continuam FAIL.
