# Feedback explícito endereçado: persistência sem voto factual

O laboratório agora registra apoio (`support`) e oposição (`oppose`) do chamador a uma candidata recuperada. Cada evento identifica exatamente a região, consulta, snapshot bruto projetado, leitura completa e candidata com todas as origens, molduras e testemunhos. O registro não altera a recuperação, escolhe respostas nem transforma apoio em verdade. A interface do MVP e o núcleo estável permanecem iguais.

## Contrato do registro

`receipt()` reconstrói a leitura nativa e aceita somente uma candidata presente nela. O recibo inclui o texto exato da consulta, hashes SHA-256 da janela projetada e da leitura completa, a candidata inteira e um identificador determinístico do próprio recibo. A janela projetada contém os cinco campos brutos usados pelo leitor, incluindo as barreiras de conteúdo gerado. Mudanças em metadados nativos fora dessa projeção não fazem parte deste contrato.

`record()` recebe um recibo, ID de evento, ID de chamador e um dos dois sinais explícitos. Antes de um evento novo, refaz a recuperação e exige igualdade integral do recibo. Consulta alterada, região indevida, candidata ausente, testemunho adulterado, snapshot antigo e campos extras não são aceitos. Nenhuma rejeição escreve no ledger.

| Operação | Comportamento |
|---|---|
| Novo ID com recibo atual | Acrescenta uma ocorrência com endereço nativo próprio |
| Mesmo ID e conteúdo integral idêntico | Retorna `EXACT_REPLAY`, sem nova ocorrência |
| Mesmo ID com ator, sinal ou recibo diferente | Rejeita conflito de identidade |
| Apoio e oposição com IDs diferentes | Preserva ambos; não calcula maioria ou vencedor |
| Observação posterior no mesmo escopo | O recibo antigo deixa de ser ativo, mesmo se a candidata permanecer |
| Reenvio exato de evento histórico já salvo | Continua idempotente; não reativa seu recibo |
| Novo recibo para a memória atual | Não herda eventos do recibo anterior |
| Reabertura nativa | Mantém eventos, endereços e leituras históricas |

IDs de eventos são locais à região; IDs dos chamadores são fornecidos pelo chamador, sem autenticação. Eventos com IDs distintos e conteúdo semelhante continuam ocorrências distintas, sem valor de voto. O exemplo de oposição não implementa detecção de contradição semântica.

O ledger usa hierarquia própria `feedback-ledger:<hash da região>`. Esse campo não entra em `collect()` da região de aprendizado; a API de recibos rejeita hierarquias do ledger como escopo de aprendizado. O envelope recebe o formato explícito `feedback-json-utf8-base64-v1:`: JSON canônico em UTF-8, codificado em Base64. Isso preserva aspas, barras, quebras de linha e Unicode do evento sem mudar a ABI existente, cuja entrada textual conserva escapes de aspas de strings JSON aninhadas. A codificação aplica-se somente ao novo envelope; não corrige nem normaliza observações de usuário na interface existente.

`addressed_feedback()` é uma consulta histórica ao recibo integral. Informa se ele ainda corresponde à leitura atual e devolve todos os eventos endereçados, inclusive os opostos. Mantém `answer=null`, `qualified=false`, `selected_target=null`, `selection_used=false` e `factual_quality_status=NOT_EVALUATED`.

## Verificações e resultados

Desenvolvimento `20261231` e reservado `20270102`: cada seed usa três cenários em símbolos legíveis e em renomeação injetiva, totalizando seis experimentos de persistência. Os cenários cobrem duas rotas com a mesma raiz, duas cores concorrentes compartilhadas pelas rotas e uma transformação errada. O último recebe feedback sobre a candidata da consulta maiúscula errada: aceitar apoio explícito não demonstra sua correção.

Em cada experimento, dois retornos opostos são gravados, um reenvio é deduplicado, cinco operações inválidas são rejeitadas, uma observação nova torna o recibo antigo histórico e um evento novo é endereçado ao novo snapshot. A reabertura verifica ledger, histórico, observações e leitura completa.

Passaram **132/132 verificações por seed**. Os relatórios completos foram repetidos e coincidiram byte a byte. A suíte de regressão passou em **73 testes**, incluindo paginação de 67 eventos, identidades com Unicode/aspas/quebras de linha, isolamento entre regiões, adulteração de testemunhos, barreira gerada posterior e substituição de todas as referências do avaliador. Essa substituição não altera o relatório: os sinais são operações explícitas programadas, não rótulos extraídos do avaliador nem aprendizado de acerto.

| Relatório | SHA-256 do objeto completo em JSON canônico |
|---|---|
| Desenvolvimento | `0f971f4a1cca90284acde13d23543836e8bc508e83fbc90a0dcfebccf310ebba` |
| Reservado | `b917669d55e0ca832398fd1f67f0f0c69f2a806714abd53b580c4a7801722744` |

Arquivos: `benchmark-results/trajectory-feedback-ledger-{development,reserved}.json`. Eles preservam observações, recibos completos, eventos endereçados e motivos das rejeições. Os testes de paginação e adulteração adicionais estão na suíte, não na contagem 132.

## Limites e próxima dependência

Isto comprova persistência e associação exata de retorno explícito no laboratório de um único escritor. Não comprova qualidade factual, compreensão de linguagem, intenção aprendida ou melhora de recuperação. O relatório declara `retrieval_improvement_status=NOT_IMPLEMENTED`. Retornos simultâneos de múltiplos processos, autenticação e transação atômica entre campo de memória e ledger não são implementados; a validação seguida de gravação exige serialização pelo chamador. A guarda de paginação é por janela, não um snapshot atômico global.

Os exemplos são correlacionados e pequenos. Apoio pode estar errado; oposição pode ser indevida. Não há pesos, penalizações automáticas, classificador de feedback em linguagem natural, integração na UI ou qualificação de resposta. O diagnóstico anterior mantém seu resultado negativo: **16/20 extras sem divergência de rotas**, além dos gêmeos de relevância indistinguíveis. Nenhum desses problemas de recuperação foi resolvido por salvar feedback.

A próxima dependência é definir e testar uma política que use retorno endereçado sem apagar conflitos ou promover sinal do chamador a fato. Essa política deverá ser avaliada separadamente contra candidatas erradas, apoio incorreto, mudanças de contexto e perdas de cobertura.

## Reprodução

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_feedback_ledger_probe.py

python scripts/trajectory_feedback_ledger_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20261231 --output /tmp/feedback-ledger-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. O commit anterior `6c6901f` passou nos oito workflows aplicáveis; trajetória no run `38086413178`. O workflow condicional foi ignorado. A CI deste incremento inclui a nova suíte e ambos os seeds e fica pendente até a execução remota.
