# Registro separado de recusas autenticadas

Continuação da [política congelada de atraso declarado](trajectory-observer-freshness-proof.md). A nova ponte opcional preserva no BDR uma observação autenticada recusada por atraso, sem inseri-la na região principal e sem criar um vínculo de resultado da hipótese. Assim, a recusa pode ser auditada depois de fechar o processo.

## Fluxo

`admit_with_rejections()` mantém a autenticação, o vínculo com a tarefa e a política congelada da etapa anterior. Se o pacote atende à regra de tick declarado, segue para a ingestão normal. Se é autenticado e defasado, chama `record_rejection()` e retorna `NOT_ADMITTED`, `link=null` e o recibo persistido.

Pacotes sem MAC válido, sem chave atualmente confiável ou inconsistentes não entram nesse registro. O recurso não arquiva entradas arbitrárias ou todos os erros possíveis. A API anterior `fresh.admit()` permanece disponível com o mesmo comportamento: uma recusa devolvida por ela não ganha persistência automaticamente.

A região nativa de controle é `observer-rejections:<hash da região principal>`. Cada recibo contém:

- Identificadores da região, hipótese e recusa.
- Envelope completo recebido, incluindo tarefa, pacote e MAC.
- Cópia da política congelada, com seu digest e identificação do recibo da hipótese.
- Avaliação de atraso declarada, com seus digests e `truth_established=false`.
- Digest do recibo anterior e digest do próprio recibo.

O registro usa a API nativa de observação em um escopo separado. Ocupa espaço no BDR; a separação demonstrada é de regiões e das leituras usadas pela auditoria, não uma sandbox física do armazenamento. Os testes comparam integralmente as linhas principais, as hipóteses e a política antes e depois de uma recusa e confirmam que permanecem iguais. A hipótese continua `PENDING`.

## Identidade e integridade

A repetição exata, inclusive após reabertura, retorna `EXACT_REPLAY` sem outra linha. A chave é verificada novamente antes disso. Reutilizar um identificador com outro envelope é erro; renomear a mesma combinação de hipótese e envelope também é recusado. Relatos autenticados distintos podem ser preservados com identificadores distintos, inclusive se seus valores discordarem: o registro não escolhe qual deles é verdadeiro.

O leitor `journal()` valida esquema, política, avaliação de atraso, digests, identidade da linha, sequência e encadeamento. Não afirma verificar a confiança atual na chave ou a autenticidade do escritor do journal. O encadeamento detecta as corrupções locais e mudanças de ordem testadas, mas não demonstra resistência a um escritor que reescreva tudo nem detecta, sozinho, remoção de um sufixo. Não há checkpoint externo, relógio autenticado ou assinatura exclusiva do auditor.

A ponte verifica a integridade estrutural desse registro antes de rotear tanto uma recusa quanto um pacote que atende à regra. Um registro corrompido causa erro antes de acrescentar uma observação principal.

## Histórico preservado e confiança atual

`review()` é somente leitura. Primeiro carrega os recibos estruturalmente válidos; depois tenta reproduzir cada avaliação com a política vinculada e a confiança atual na chave:

| Estado da revisão | Significado |
|---|---|
| `REVERIFIED_STALE` | A avaliação de atraso pôde ser reproduzida sob a configuração atual |
| `CURRENT_VERIFICATION_FAILED` | A verificação atual falhou; a razão é devolvida, sem apagar o recibo original |

Uma revogação posterior não apaga a recusa nem transforma o pacote em falso. Apenas impede reivindicar que ele passou pela verificação atual. O mesmo tratamento conserva o registro quando a versão esperada do trabalhador muda ou quando o prefixo de memória da hipótese deixa de ser reproduzível. A revisão pode voltar a passar se o chamador restaurar a confiança/configuração; esta etapa não implementa revogação global irrevogável ou histórico versionado de políticas de chave.

A estrutura do recibo pode ser lida sem a chave. Essa leitura isolada não comprova que o pacote era autêntico quando foi registrado; o caminho normal de gravação exige a autenticação e o ambiente local permanece confiável. Segredos não são gravados; o experimento continua usando uma fixture pública de chave, sem implantação de identidade real.

## Resultados positivos e negativos

| Controle | Resultado preservado |
|---|---|
| Leitura autenticada e defasada | Envelope completo retido no controle; região principal e hipóteses inalteradas |
| Mesma recusa repetida | Sem duplicação |
| Mesmo envelope com outro identificador | Erro sem outra escrita |
| Identificador reaproveitado com outro relato | Erro sem outra escrita |
| Chave retirada antes da gravação | Nada gravado |
| Chave retirada depois da gravação | Recibo mantido; revisão atual falha |
| Pacote alterado sem MAC correspondente | Nada gravado |
| Leitura com tick atual | Segue pela ingestão anterior, sem recibo de recusa |
| Valor falso autenticado com tick atual | Também passa pela regra; continua sem promoção factual |

A avaliação não consulta a lei do mundo. Um teste faz `world_value()` lançar uma exceção e confirma que a gravação da recusa e sua revisão não dependem dessa função. A lei da simulação é usada somente no avaliador posterior dos relatórios. Recusas não geram feedback, correção de pesos, nova candidata principal ou escolha factual. A ingestão normal de um pacote admitido mantém seus efeitos anteriores.

## Evidência reproduzível

- 96 testes locais aprovados: 18 novos e 78 anteriores.
- Sementes `20270125` e `20270126`: 124/124 verificações de integridade em cada uma.
- Recibo completo, política, linhas principais e revisão reproduzidos em dois processos sucessivos.
- Cobertos conflitos entre relatos, repetição, revogação, mudança de versão, prefixo histórico alterado e corrupção de digest/identidade/ordem/encadeamento.
- Os dois relatórios anteriores de atraso declarado foram reproduzidos byte por byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_observer_rejection_probe.py \
  tests/test_trajectory_observer_freshness_probe.py \
  tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_observer_rejection_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270125 \
  --output /tmp/observer-rejection-development.json.gz
```

Repetir com `20270126` para a amostra reservada. Artefatos integrais em `benchmark-results/trajectory-observer-rejection-{development,reserved}.json.gz`, incluindo entradas, envelopes, recibos, revisões, erros e confronto. O CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara integralmente os relatórios descomprimidos.

Há um único escritor e nenhuma transação conjunta entre todas as regiões. Uma falha de flush pode deixar o resultado da escrita incerto; a recuperação usa repetição exata. Não há política de retenção, limite total de recibos ou prova de completude do journal. Núcleo, ABI móvel, MVP e console permanecem preservados. Qualidade do valor, identidade pública, previsão inédita e aprendizado por erro continuam lacunas separadas.
