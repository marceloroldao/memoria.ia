# Admissão experimental com chave compartilhada

Continuação do [observador separado](trajectory-controlled-observer-proof.md). Esta etapa acrescenta uma ponte opcional que verifica HMAC-SHA256 antes de registrar uma observação. O escopo demonstrado é posse da chave compartilhada configurada para uma fonte e um identificador de chave. Não é identidade pública, PKI, assinatura exclusiva do sensor ou julgamento de verdade.

## Contrato

`freeze_task()` congela região, identificador da hipótese, consulta formal, fonte esperada, identificador de chave, desafio aleatório de 32 bytes, solicitação ao mundo e hashes dos arquivos do trabalhador e do mundo simulado. A fonte e o identificador de chave são nomes configurados pelo chamador. A consulta deve corresponder à entidade da solicitação.

O trabalhador `authenticated_symbol_observer.py` recebe somente essa tarefa e a chave por stdin. Não recebe candidatas ou caminho do BDR. Produz um envelope com a tarefa, o pacote completo de observação e o MAC. O MAC cobre todos esses campos com prefixo de domínio próprio. A implementação usa `hmac.new(..., 'sha256')` e `hmac.compare_digest()`, conforme a [documentação oficial do Python](https://docs.python.org/3/library/hmac.html).

A chave não entra no journal, no recibo ou no relatório. O protocolo do trabalhador não imprime a chave ou o conteúdo de erros. Isso não garante isolamento do segredo do processo pai, depurador ou sistema operacional. O processo pai/verificador também possui a chave e pode produzir envelopes válidos. O mínimo de 32 bytes é validado, mas a aplicação não consegue verificar a entropia escolhida pelo operador.

`ingest_result()` busca a tarefa congelada, exige uma chave atualmente presente no mapa `(source_id, key_id) -> bytes`, verifica o envelope e a integridade do pacote e só então faz a ingestão normal e o vínculo no journal. Pacotes de outra fonte, desafio ou tarefa são recusados. Trocar região, hipótese, consulta ou versões também altera o contrato autenticado.

O desafio padrão é gerado com `secrets.token_hex(32)` ao criar a tarefa. O parâmetro explícito existe para reprodução dos testes. Em uso real, o chamador deve preservar o desafio da tarefa original ao repeti-la e não reutilizá-lo para outra aquisição. A API não administra chaves, expiração, relógios, certificados ou armazenamento seguro. A política atual é o mapa fornecido em cada chamada; removê-lo representa revogação nessa chamada, não uma revogação global persistida.

## Separação entre admissão, histórico e verdade

`authenticate_history()` relê os envelopes persistidos e verifica sua autenticação usando a política atual, inclusive após reabertura nativa. Retorna a contagem verificada e o escopo `CONFIGURED_SHARED_KEY_POSSESSION`, com `truth_established=false` e `nonrepudiation=false`. Uma chave retirada ou trocada faz essa verificação falhar; nenhum resultado antigo é apagado.

O confronto comum `reconcile()` continua sem autenticar e sem aprender: `answer=null`, `qualified=false`, `learning_applied=false` e `provenance_independence=NOT_ESTABLISHED`. Para uma leitura completa, executar tanto o confronto quanto a autenticação explícita. A autenticação isolada não verifica toda a cadeia temporal ou a presença atual da ocorrência; essas verificações continuam na auditoria.

A API genérica de auditoria permanece disponível e aceita vínculos sem autenticação. Portanto esta ponte não é uma fronteira de segurança global do projeto. Um teste injeta um vínculo pela API genérica e confirma que `authenticate_history()` o rejeita sem alterar a memória. O consumidor deve exigir a ponte e a verificação explícita quando precisar desse contrato.

A ingestão normal conserva seus efeitos anteriores; a comparação não adiciona feedback, pesos ou promoção factual. A identidade da ocorrência usa o mesmo digest do pacote da ponte anterior. Novo MAC, desafio ou identificador de resultado não fabrica uma sequência mais recente para o mesmo pacote. Uma leitura nova exige uma solicitação diferente. A ponte continua com um escritor e duas escritas sequenciais, sem transação conjunta entre observação e vínculo.

## Controles positivos e negativos

| Cenário | Admissão pela ponte | Confronto ou limite |
|---|---|---|
| Leitura fiel com chave esperada | Aceita | Valor novo permanece fora do conjunto congelado |
| Leitura defasada com chave esperada | Aceita | Coincide com candidata antiga, mas discorda do mundo no tick solicitado |
| Valor alterado e checksum recalculado, sem novo MAC | Recusada antes de escrever | Fecha o controle de falsificação sem chave da etapa anterior |
| Chave errada | Recusada antes de escrever | MAC inválido |
| Outra fonte com a mesma chave de teste | Recusada antes de escrever | Fonte não corresponde à tarefa |
| Outro desafio | Recusada antes de escrever | Aquisição não corresponde à tarefa |
| Chave retirada da política | Recusada antes de escrever | Fonte/chave sem confiança atual |
| Relato falso com MAC recalculado pelo detentor da chave | Aceita | Autenticação válida, leitura errada; sem promoção a fato |

O último caso é deliberado: autenticação não resolve qualidade, desatualização ou comprometimento de um detentor da chave. Ambos os relatos errados aceitos continuam sem qualificação factual. O avaliador consulta a lei do mundo somente depois da ingestão e não a usa para aceitar, aprender ou corrigir valores.

## Evidência reproduzível

Os testes usam uma chave sintética pública, identificada no código, exclusivamente como fixture. Os relatórios não demonstram posse de uma chave de produção. Não se deve reutilizar essa fixture em uma implantação.

- 58 testes locais aprovados: 23 novos e 35 anteriores.
- Sementes `20270121` e `20270122`: 70/70 verificações de integridade em cada uma.
- Reabertura nativa, repetição exata, revogação na releitura, escopo autenticado, conflito de identificador, pacote inconsistente mesmo com MAC válido e impossibilidade de fabricar posterioridade cobertos.
- Os dois relatórios do observador anterior foram reproduzidos byte por byte.
- CI dedicado reconstrói o runtime com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a` e compara integralmente os relatórios descomprimidos.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
  python -m pytest -q tests/test_trajectory_authenticated_observer_probe.py \
  tests/test_trajectory_controlled_observer_probe.py tests/test_trajectory_prediction_audit.py
PYTHONPATH=src python scripts/trajectory_authenticated_observer_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --seed 20270121 \
  --output /tmp/authenticated-observer-development.json.gz
```

Repetir com `20270122` para a amostra reservada. Artefatos em `benchmark-results/trajectory-authenticated-observer-{development,reserved}.json.gz` preservam entradas, tarefas, envelopes, recusas, confronto, avaliação posterior e verificações.

| Amostra | SHA256 do conteúdo registrado no relatório |
|---|---|
| Desenvolvimento | `82ef348b0a335866edc5aed694621f148c3ba3097e91f74d83c1135be5ad2018` |
| Reservada | `ef1811b26bf7d2aaaffa71f55e9b6c2d5dd251b023708bc4dcc294f86b67bc11` |

O núcleo cognitivo, a ABI móvel e as interfaces de produto não foram alterados. Permanecem separadas as lacunas de identidade assimétrica, qualidade da medição, previsão de valores inéditos e aprendizado por erro. Esta etapa não comprova verdade externa, segurança de produção ou aprendizado geral.
