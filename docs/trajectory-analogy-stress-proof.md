# Diversidade de formas e contraexemplo de relação misturada

## Resultado

O seletor de molduras anterior permanece inalterado e separado do motor. Novo scorecard opaco testa 12 famílias, sete consultas e renomeação bijetiva: **128/168 critérios por lote**, respostas corretas **8/44**, ausência com zero candidatos **120/124**, quatro seleções únicas incompatíveis com o contrato do avaliador. Qualidade **FAIL**.

| Família | Critérios por lote | Limite observado |
|---|---:|---|
| Moldura simples | 14/14 | Transferência sustentada e controles de ausência passam |
| Campo de relação invariável | 14/14 | Transferência sustentada e controles de ausência passam |
| Valores de treino idênticos | 10/14 | Não aprende a moldura com três valores distintos |
| Dois valores de treino iguais | 10/14 | Mesmo limite conservador |
| Variável copiada duas vezes | 10/14 | Formato anterior exige ocorrência única |
| Cópia em ordem invertida | 10/14 | Formato anterior exige cópia contígua na mesma ordem |
| Origem sem prefixo comum | 10/14 | Âncora exigida ausente |
| Origem sem sufixo comum | 10/14 | Âncora exigida ausente |
| Identificador contém o prefixo da consulta | 10/14 | Veto de duas ocorrências do prefixo também impede consulta válida |
| Valores compartilham prefixo incidental | 10/14 | Esse prefixo vira literal da moldura e bloqueia valor novo |
| Valores compartilham sufixo incidental | 10/14 | Mesmo limite na terminação |
| Campos de relação misturados | 10/14 | Quatro seleções únicas indevidas segundo o contrato do teste |

As nove famílias de cobertura limitada somam 36 abstenções em consultas que o avaliador exige responder. Essas abstenções continuam contadas como falhas. A família misturada produz quatro falhas de ausência; também permanecem no scorecard. Não adotamos um filtro para esconder essas falhas nem alteramos os critérios anteriores.

## Contraexemplo

O gerador do fixture separa no destino: prefixo, variável copiada, separador, campo de relação, separador interno, valor e sufixo. No controle positivo, o campo de relação é igual nos três exemplos. No controle misturado, cada exemplo tem um campo diferente. As origens e consultas dos dois controles são exatamente iguais; os campos de relação não são fornecidos ao seletor como metadados.

A moldura anterior guarda somente prefixo/sufixo do trecho após a variável copiada. Na família misturada, ela absorve **campo de relação + separador interno + valor** dentro de um único valor livre. Um payload isolado com um quarto campo, nunca observado nos três pares, passa nessa moldura ampla e vira hipótese única.

O contrato desta bateria exige abstenção quando não há campo de relação invariável observado. A seleção é incompatível com esse contrato; o payload escolhido foi realmente observado e não é um texto inventado. O caso evidencia a ambiguidade de fronteiras entre relação e valor. Não demonstra que esse campo seja dedutível sem novas hipóteses ou que todo padrão amplo seja inválido. O sucesso anterior em molduras estreitas não assegura a seleção correta sob esse contrato mais exigente.

As quatro falhas por lote correspondem a pergunta conhecida/prefixo novo e suas versões renomeadas do mesmo contraexemplo. Não são quatro exemplos independentes. Seeds 20261016 e 20261017 apenas mudam os endereços numéricos, preservando a geometria das mesmas 12 famílias; o segundo lote não introduz novos domínios ou formas.

## Verificação e limites

Cinco testes verificam os controles invariável/misturado, recuperação da raiz correspondente, reprodução e pontuação da seleção indevida, abstenções positivas contadas como falhas e invariância à renomeação. Cada leitura verifica resultado após restauração, GenerationResult completo e snapshot/estado de aprendizado intactos. Perguntas, resultados e rótulos não entram no aprendizado; os exemplos são os únicos pares observados. Os relatórios preservam exemplos, raízes isoladas, consultas, candidatos, molduras, testemunhas e geração padrão completos.

Executar `python scripts/trajectory_analogy_stress_probe.py --seed 20261016` e `--seed 20261017`. O modo padrão verifica integridade/reprodução e retorna zero mesmo com qualidade FAIL; `--strict-quality` retorna 1. Esta bateria é Python, sem nova execução pela ABI nativa. O job nativo anterior continua sendo executado no mesmo workflow para conservar as provas anteriores.

Motor, seletor de molduras, política padrão, pesos, runtime e OFF.IA não mudaram. O resultado anterior da analogia continua 116/140 com suas condições de treinamento; a opção contextual anterior permanece 26/32 e o gate nativo original 23/26. PR draft.

Próxima questão: como preservar âncoras internas e múltiplos campos possíveis, expondo a ambiguidade em vez de absorvê-la em um único valor livre. Antes de integração, também permanece necessário ampliar a cobertura e medir custo de descoberta.

## Validação concluída

[Workflow 36901870221](https://github.com/marceloroldao/memoria.ia/actions/runs/36901870221) passou no commit `77862339285e73578039f0ae2bb8aa5cb02b47dd`: cinco testes novos, 59 do gerador, 18 da hipótese padrão, oito da opção contextual e 66 regressões (um BDR opcional pulado), além dos controles anteriores. Todos os outros workflows aplicáveis passaram; experimental PR regression foi pulado pela condição existente.

Os dois relatórios completos dos logs coincidem exatamente, campo a campo, com os relatórios locais. Ambos confirmam **FAIL 128/168**, respostas 8/44, ausência vazia 120/124 e quatro seleções únicas incompatíveis com o contrato. Dados completos em `benchmark-results/trajectory-analogy-stress-{development,reserved}.json`. Os cinco lotes padrão preservaram PASS 150/150. No mesmo workflow, a execução nativa anterior confirmou analogia FAIL 116/140 e opção contextual FAIL 26/32, sem mudanças nesses scorecards.

O modo estrito foi executado localmente no segundo lote e retornou 1 diante de FAIL. O sucesso de CI é de integridade/reprodução; não aprova a política de analogia. Sua integração permanece pendente, com este contraexemplo registrado e sem alteração do seletor.
