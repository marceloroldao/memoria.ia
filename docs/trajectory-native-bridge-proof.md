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

## Cenários e pré-verificação local

| Cenário | Situação | Critérios locais |
| --- | --- | --- |
| legacy_isolated | Os dez registros iniciais do gate pessoal, sem relações ordenadas pergunta/resposta entre capturas | 2/8, FAIL |
| ordered_pairs | Pergunta/resposta observadas na mesma captura para drone e robô | 2/8, FAIL |
| ordered_conflict | Acrescenta outra resposta observada para a pergunta do drone | 6/8, FAIL |
| assistant_barrier | Pergunta, saída gerada, usuário posterior; par independente para robô | 8/8, PASS |

São quatro consultas em dois adaptadores por cenário: conhecida, prefixo novo,
outro sujeito e recombinação ausente. Os adaptadores do mesmo texto não são casos
independentes. Antes da execução nativa, o adaptador com os mesmos registros
fornecidos localmente dá 18/32 critérios, 2/16 respostas corretas e zero hipóteses
indevidas. Esta pré-verificação não comprova leitura de BDR nem execução da ABI.

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
