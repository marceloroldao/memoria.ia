# Variações observadas: prova adversarial, 30/09/2026

## Resultado

O gate mais amplo **falha** sem alterar o motor do commit
`9634417cbf635dd14350213a0d7e9f472e498eec`. Aprender uma segunda superfície
seguida do mesmo destino recupera o alvo, mas também pode produzir fragmentos
concorrentes e aceitar uma pista comum genérica para outro sujeito.
Os quatro lotes anteriores continuam passando em 52/52; isso não demonstra
generalização para estas novas condições. Não há integração em OFF.IA.

| Lote / seed | Critérios | Respostas corretas | Hipóteses indevidas | Qualidade |
| --- | --- | --- | --- | --- |
| Desenvolvimento / 20260930 | 118/150 | 34/54 | 12 | FAIL |
| Segundo lote / 20261009 | 120/150 | 34/54 | 10 | FAIL |
| Reserva / 20261010 | 118/150 | 34/54 | 12 | FAIL |

## Método reproduzível

`python scripts/trajectory_observed_variant_probe.py --seed 20261010 --strict-quality`

O comando imprime o relatório completo e retorna **1**, pois qualidade falha.
Sem `--strict-quality`, retorna zero depois de verificar integridade e expõe
`quality_status: FAIL`. O novo passo de CI verifica contratos e reporta qualidade;
sucesso do workflow não é aprovação deste gate de qualidade.

Cada lote contém dois cenários textuais fictícios nos adaptadores Unicode e UTF-8
e um cenário opaco com duas renomeações bijetivas. São seis fixtures, cinco etapas
e cinco consultas por etapa, totalizando 150 critérios. Adaptadores sobre o mesmo
texto são correlacionados; os 50 critérios opacos são iguais nos três lotes.
O segundo e terceiro seeds foram executados após fixar o avaliador.

Etapas independentes, reconstruídas desde uma memória vazia:

1. `unseen`: pergunta original seguida do destino; variação nunca observada.
2. `source_only`: acrescenta a variação isolada, em outra captura, sem destino.
3. `paired`: observa a variação seguida do destino já armazenado, na mesma captura.
4. `repeated`: repete duas vezes esse par, com IDs novos e conteúdo reutilizado.
5. `conflict`: observa a variação seguida de outro destino, em captura independente.

As consultas verificam original, variação, prefixo inédito sobre a variação,
sujeito desconhecido e assunto sem relação. Uma pergunta sem destino observado
deve permanecer sem hipótese; observar só a pergunta não ensina a resposta.
Conflitos exigem retenção dos dois destinos completos e abstenção. O original
continua tendo seu próprio par observado, e sua resposta é avaliada separadamente.

Os rótulos e as transformações de caixa pertencem exclusivamente ao avaliador.
O motor recebe sequências de inteiros, ordem, IDs e capturas. Não recebe nomes,
classes semânticas, equivalência de caixa ou resposta esperada. Cada consulta
compara snapshot/learning_state antes e depois e paridade de GenerationResult e
hipótese após reabertura. O conteúdo único é contado por raiz, não por ocorrência;
as quatro ocorrências adicionais em `repeated` não aprendem conteúdo nem pares novos.

## Contrastes que orientam a próxima correção

No desenvolvimento, `unseen` e `source_only` passam em 30/30 cada. O original é
respondido, mas a variação não recebe uma resposta por simples semelhança.

Em `paired` e `repeated`, os 18/18 casos com resposta esperada retêm o alvo,
mas apenas 10/18 selecionam corretamente. Nos oito casos textuais de variação
e prefixo, o modo COMBINED_RECALL mantém a resposta aprendida junto com fragmentos
estruturais e a hipótese se abstém. Nos quatro controles textuais de sujeito
desconhecido por etapa, a hipótese escolhe um fragmento indevido. Repetir os mesmos
payloads não muda esses resultados; repetir conteúdo não cria votos novos.

Os controles opacos passam em todas as etapas, incluindo prefixo novo, conflito,
sujeito desconhecido e renomeação. Isto verifica invariância estrutural nesta fixture,
não equivalência linguística. Os conflitos textuais retêm ambos os destinos e se
abstêm; entretanto, o conflito também interfere na seleção da pergunta original.

A próxima proposta deve separar a sustentação da raiz completa consultada das
rotas apoiadas somente no trecho comum entre diferentes superfícies. Não basta
aceitar todo COMBINED_RECALL nem reduzir genericamente o contexto exigido: isso
precisa preservar ausência, destinos divergentes, alvos transportados e consultas
novas com uma pista curta legítima. Esta etapa não implementa tal política.

## Validação e limites

Quatro testes do avaliador passaram: fragmento incorreto não equivale a resposta;
conflito exige ambos os alvos e abstenção; pergunta isolada não aprende resposta e
conteúdo repetido é reutilizado; renomeação bijetiva preserva qualidade/hipótese.
59 testes do gerador passaram. Os quatro gates anteriores foram repetidos com
`--strict-quality` e mantiveram PASS 52/52. Os arquivos locais existentes de código
e dos probes usados foram comparados com a árvore publicada, ignorando apenas
linhas vazias finais. A tentativa local de regressão pytest não executou porque
pytest não está instalado; o workflow contém a instalação e execução completas.

Relatórios completos, com entradas fictícias, recibos, candidatos e contextos:
`benchmark-results/trajectory-observed-variant-{development,heldout,reserved}.json`.
O motor, pesos e seleção padrão não foram alterados. A nova bateria expõe uma
limitação antes não coberta. Não mede acurácia real, cognição ou substituição de LLM.
PR permanece draft; os três gates pessoais nativos anteriores seguem pendentes.
