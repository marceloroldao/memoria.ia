# Trecho transportado dentro de um fragmento misto

## Resultado

A revisão da opção `transported_source_scope=True`, ainda desativada por padrão, melhora a comparação da ponte de **24/32 para 26/32** critérios. Respostas corretas passam de **8/16 para 10/16**. Os dois critérios recuperados são a pergunta do robô no fixture que contém dois destinos conflitantes para o drone, nos adaptadores Unicode e UTF-8. São versões correlacionadas do mesmo cenário.

| Fixture fictício | Opção anterior | Revisão |
|---|---:|---:|
| Capturas isoladas | 2/8 | 2/8 |
| Pares ordenados | 8/8 | 8/8 |
| Pares com conflito | 6/8 | 8/8 |
| Barreira do assistente | 8/8 | 8/8 |
| Total | 24/32 | 26/32 |

Mantém ausência 12/12, conflitos 4/4 e zero hipóteses diferentes do alvo esperado na bateria. A qualidade geral continua **FAIL**. Os seis critérios restantes são perguntas com alvo esperado nas capturas isoladas, que não observaram uma relação temporal de resposta. O avaliador mantém esses critérios e não conta abstenção como resposta correta.

## Mudança

Na consulta do robô, o nódulo concorrente recuperado é `Meu drone se chama `. Esse fragmento mistura o trecho copiado `eu drone`, presente na pergunta de origem, com símbolos introduzidos no destino. A versão anterior exigia que o fragmento inteiro estivesse na origem, impedindo a consolidação.

A revisão examina subtrechos contíguos do fragmento, com largura mínima `config.min_context`, do maior ao menor. Para discriminar os pares de origem/destino/captura desse fragmento, **um mesmo subtrecho precisa estar em todas as origens e destinos testemunhas**, e ausente da consulta, das pistas completas que sustentam o destino escolhido e desse destino. Não combina pedaços de origens diferentes para formar o discriminador. O fragmento inteiro pode incluir conteúdo introduzido; a opção só o deixa fora do escopo se todos os seus pares forem cobertos.

Não acrescenta normalização, vocabulário de sujeitos ou classificação de verdade. Conserva os vetos de destinos completos, truncamento, consulta contendo o discriminador, origens contendo uma pista completa e origens sem suporte próprio/discriminador. A auditoria dos pares de raízes observados continua cobrindo evidência que deixou de aparecer depois da descoberta composicional mudar.

`GenerationResult`, `selected`, todos os candidatos, pesos, testemunhas, snapshots e aprendizado permanecem intactos. Na pergunta do robô, os dois pares do drone ficam explicitamente em `scoped_out_witnesses` e seu fragmento continua visível. Na pergunta do drone, as respostas completas Auri/Boreal continuam presentes e a hipótese se abstém.

## Testes e reprodução

Oito testes da opção passaram localmente, incluindo os seis anteriores e dois novos: fragmento misto recupera o outro sujeito sem ocultar conflito de raiz, com adaptadores, renomeação bijetiva e prefixo inédito; subtrechos transportados diferentes em testemunhas distintas não autorizam consolidação. O teste agregado também executa os **18 contratos anteriores com a opção habilitada**. Os 18 testes padrão da hipótese e 59 do gerador passaram.

O script `trajectory_transported_scope_probe.py` passa a emitir formato `memoria.ia-transported-source-scope-v2`, revisão `transported-common-subspan-v1`. Mantém `--library` para comparação via janelas frias nativas e `--strict-quality` para retornar 1 enquanto 26/32 continuar FAIL. O runtime nativo é compilado sem mudanças, com o mesmo BDR fixado. A inferência experimental acontece apenas em Python após ler a janela.

Relatórios da versão anterior permanecem preservados e vinculados a seus commits. Esta revisão não altera a política padrão, não ativa a inferência em OFF.IA e não resolve as três falhas do gate nativo original 23/26. A ponte padrão continua 18/32; PR draft.

## Validação concluída

[Workflow 36889290751](https://github.com/marceloroldao/memoria.ia/actions/runs/36889290751) passou no commit `d2da278cc16f6898bc0ea8635dbff10c45919f55`: oito testes da opção (incluindo os 18 contratos habilitados), 18 testes padrão da hipótese, 59 do gerador e 66 regressões (um BDR opcional pulado), além dos controles anteriores. Os cinco lotes padrão de variações preservaram PASS 150/150. Todos os outros workflows aplicáveis passaram; experimental PR regression foi pulado por sua condição existente.

O job nativo confirmou a revisão **FAIL 26/32**, respostas 10/16, ausência 12/12, conflitos 4/4 e zero hipóteses diferentes do alvo esperado na bateria. O relatório nativo completo preserva proveniência, ordem e reabertura. Todos os campos comuns coincidem exatamente com o diagnóstico local, incluindo casos e testemunhas. Relatório dos logs salvo em `benchmark-results/trajectory-transported-subspan-report.json`. O modo estrito foi executado localmente e retornou 1, corretamente, diante de 26/32 FAIL.

O lote anterior com a opção habilitada, seed 20261014, continua PASS 150/150; seu relatório JSON completo coincide exatamente com o anterior depois de alinhar somente o nome da revisão. Após fixar implementação e oito contratos, executamos localmente um novo lote habilitado, seed **20261015**: PASS 150/150, respostas 54/54 e zero hipóteses indevidas. Esse lote não foi executado no CI nem na ABI nativa. Dados completos em `benchmark-results/trajectory-transported-subspan-reserved.json`, com revisão e ambiente explícitos. Adaptadores e controles opacos continuam correlacionados; não representam casos independentes de uso real.

Próxima pendência: avaliar recuperação estrutural nas capturas sem pares de resposta observados, sem ensinar os rótulos do avaliador ou reaprender consultas e saídas geradas. Os seis critérios restantes permanecem no relatório como falhas.
