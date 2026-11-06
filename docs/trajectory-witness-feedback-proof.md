# Rejeição de uma ocorrência de demonstração

Continuação: [transferência de feedback em consultas reservadas e regimes de redundância](trajectory-feedback-transfer-stress.md), com retornos corretos/incorretos programados e referências isoladas do aprendizado.

O novo leitor `trajectory_witness_feedback_probe.py` acrescenta o alvo `WITNESS` ao contrato de feedback endereçado. Ele identifica uma ocorrência nativa de demonstração: uma entrada de origem e a entrada de destino adjacente no mesmo fluxo elegível da região. Isso permite rejeitar o uso daquela ocorrência sem declarar o conteúdo falso em todos os contextos ou rejeitar diretamente uma moldura inteira.

O mecanismo é uma política experimental de dependências, desativada por padrão. Não decide autonomamente qual demonstração está errada e não altera os pesos ou as observações do núcleo. Todas as molduras e candidatas brutas continuam visíveis.

## Endereçamento e prova de origem

O alvo solicitado contém:

```python
target = {
    "kind": "WITNESS",
    "frame_id": selected_frame_id,
    "witness": [source_payload_id, target_payload_id, stream_id],
    "source_address": [region, source_id, source_sequence],
    "target_address": [region, target_id, target_sequence],
}
record_addressed(native, binding, "decisao-1", "operador", "oppose", target)
view = witness_read(native, region, query, enabled=True)
```

A moldura precisa ter gerado a candidata do recibo atual, e o testemunho precisa pertencer a essa moldura. Seus payloads e segmento são resolvidos pelo adaptador inalterado para pares de ocorrências reais. Os dois endereços precisam identificar exatamente um desses pares. Endereços inexistentes, invertidos, de outra região, não adjacentes ou de conteúdo gerado são recusados antes de escrever.

São preservados os cinco campos da projeção nativa de cada entrada: região, ID de origem, sequência, texto e tipo de origem. A adjacência é a do fluxo elegível daquela região/segmento, não a de todas as conversas intercaladas. Conteúdo gerado quebra o segmento; não vira demonstração. Repetições do mesmo payload mantêm endereços de ocorrência distintos.

O evento guarda o recibo integral, a moldura de origem como âncora, o testemunho e o par exato. Na leitura, o prefixo histórico precisa reproduzir o recibo e esse alvo; o par atual precisa coincidir integralmente com o capturado. A âncora demonstra como o alvo foi endereçado. O efeito segue a dependência do mesmo testemunho no escopo, inclusive em outras molduras que o utilizem; não fica limitado ao ID da moldura original.

## Regra de disponibilidade

Uma moldura depende de seus três pares distintos observados. O novo leitor resolve cada testemunho para todas as ocorrências que o sustentam. Ela fica indisponível se algum testemunho necessário não tem nenhuma ocorrência sobrevivente. Rejeitar uma entre duas ocorrências do mesmo par não esgota esse suporte. Rejeitar ambas pode esgotá-lo; retirar uma rejeição devolve uma ocorrência disponível.

Uma candidata continua disponível quando alguma moldura geradora permanece válida e não há veto de conteúdo ou moldura pela política anterior. Contar várias molduras não prova que elas sejam independentes: todas podem compartilhar uma demonstração necessária para a consulta.

As observações não são removidas, nem filtradas antes da reconstrução das molduras. Isso evita criar adjacências novas ligando artificialmente as entradas que sobrariam. O inventário bruto de molduras/candidatas permanece igual após uma operação de feedback. O leitor apenas mascara dependências esgotadas. O relatório reúne cada testemunho com sua lista de molduras consumidoras e suas ocorrências, evitando cópias redundantes sem perder o mapeamento.

`CONTENT`, `FRAME` e `WITNESS` continuam decisões diferentes e reversíveis. Rejeitar uma moldura inteira pode mantê-la bloqueada mesmo após retirar a rejeição de um testemunho. Apoio não remove oposição, não promove conteúdo e não aumenta confiança factual. O mesmo journal append-only e as retiradas endereçadas da etapa anterior são reutilizados.

O leitor `addressed_read(enabled=True)` recusa controles `WITNESS` ativos e exige o leitor novo, para não aplicá-los parcialmente. Seu modo desativado continua expondo a recuperação bruta. Isso não integra o recurso aos consumidores que não leem esse journal: console, MVP, OFF.IA e seletores padrão continuam fora deste experimento.

## Bateria controlada

Seeds `20270113` e `20270114`, seis cenários em texto legível e sob renomeação injetiva, 12 experimentos por seed. As consultas de transferência e seus payloads não são alvos de feedback. O chamador programado escolhe ocorrências pela proveniência e dependências observadas, sem usar as referências do avaliador. Estas só pontuam os resultados finais.

Nos controles de cobertura, a escolha é explícita: um testemunho que aparece em todas as molduras da candidata original, ou um para o qual existe uma moldura alternativa. A seleção é ordenada pelos endereços nativos de origem/destino, não por ordem de hashes de payload. São intervenções pequenas e correlacionadas, não uma medida geral de acurácia.

Contagens na segunda consulta: **esperados recuperados / extras / perdas**.

| Cenário | Antes | Depois | Resultado |
|---|---|---|---|
| Rejeitar a ocorrência que sustenta uma rota extra única | 1 / 1 / 0 | 1 / 0 / 0 | A dependência esgotada suspende o extra |
| Rejeitar uma demonstração correta necessária | 1 / 0 / 0 | 0 / 0 / 1 | A decisão errada propaga uma perda |
| Outra moldura apoiada em demonstrações diferentes | 1 / 1 / 0 | 1 / 1 / 0 | O extra sobrevive pelo caminho alternativo |
| Outra ocorrência do mesmo par no mesmo segmento | 1 / 1 / 0 | 1 / 1 / 0 | Rejeitar uma ocorrência não rejeita automaticamente a outra |
| Relevância diferente oculta no avaliador | 1 / 1 / 0 | 0 / 1 / 1 | Entradas e leituras idênticas não distinguem a intenção oculta |
| Várias molduras dependem do mesmo testemunho necessário | 1 / 1 / 0 | 1 / 0 / 0 | Quatro demonstrações não garantem suporte independente para os símbolos consultados |

Nos casos alternativos, preservar disponibilidade também preserva um erro do contrato do avaliador. Essa é uma limitação medida, não uma melhora factual. Um teste adicional mostra que acrescentar a mesma demonstração rejeitada em outro segmento/endereço pode criar outra moldura e restaurar o extra, mesmo com a rejeição antiga ativa. A operação endereça uma ocorrência, não proíbe um texto universalmente.

Todos os cenários verificam preservação das entradas e da leitura bruta, ausência de escrita por consulta, par nativo exato, reenvio idempotente, modo desativado, retirada e igualdade integral após reabrir o BDR. Os gêmeos preservam observações, recibos, operações e leituras completas; somente a referência do avaliador muda.

## Diagnóstico durante a construção da bateria

A primeira versão escolhia o primeiro testemunho pela ordem de IDs de payload e teve **138/139 verificações**, falhando no controle de renomeação do cenário alternativo. A ordenação podia escolher outra demonstração após renomear. Identificar um índice fixo de demonstração também não definiu a mesma classe de cobertura entre os dois seeds: os exemplos lexicais distribuem os símbolos necessários de maneiras diferentes.

O protocolo final escolhe uma classe de dependência observável e endereça a ocorrência real correspondente. O caso de testemunho compartilhado foi acrescentado para preservar a descoberta: mais demonstrações ou molduras não implicam cobertura independente. Isso corrige a definição da intervenção de controle; não demonstra que rejeições arbitrárias sejam seguras ou que o leitor tenha aprendido a julgar causalidade.

## Validação e reprodução

**36 testes locais passaram:** 17 novos de testemunhos e 19 regressões de alvos `CONTENT`/`FRAME`. Os novos testes cobrem rejeição de uma e de duas ocorrências, caminhos alternativos, dependência compartilhada, feedback errado, repetição em novo endereço, alvos adulterados/gerados, independência das retiradas, leitores incompatíveis e reabertura. Um contrato de par exato/reabertura foi repetido após compactar os diagnósticos. Compilação Python e `git diff --check` passaram. Sem biblioteca implícita, os 17 testes novos foram pulados como esperado; na CI nativa o caminho é explícito.

Ambos os seeds passam em **166/166 verificações de integridade**. Os relatórios completos finais são repetidos e comparados byte a byte. Os dois relatórios anteriores de `CONTENT`/`FRAME` também foram reproduzidos e continuaram exatamente iguais aos já versionados.

| Relatório | Digest, excluindo `report_content_sha256` |
|---|---|
| `benchmark-results/trajectory-witness-feedback-development.json` | `93c3f92d7465c14b7f5b38f56b4b5c5d7c6c307ee0cdda7d476061c581790b22` |
| `benchmark-results/trajectory-witness-feedback-reserved.json` | `2f48f4e5f5c19b4d29fc2f4ca6ddab2febf061970551f703f35980a576ecdbef` |

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_witness_feedback_probe.py \
  tests/test_trajectory_addressed_feedback_probe.py

PYTHONPATH=src python scripts/trajectory_witness_feedback_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270113 --output /tmp/witness-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. O job focado `addressed-feedback` mantém as verificações anteriores e acrescenta testes de testemunhos, ambos os seeds e comparação integral com os novos relatórios. A aprovação remota precisa ser conferida no commit publicado. O commit anterior `60c6b9b` terminou com os oito workflows aplicáveis aprovados, incluindo a bateria cumulativa de trajetórias; o condicional foi ignorado.

## Limites e próxima investigação

O sistema agora representa uma dependência em ocorrências precisas e preserva alternativas observadas. Não descobre autonomamente erros, não valida fontes e não aprende pesos numéricos. Uma rejeição errada pode remover uma resposta correta; alternativas ou novas ocorrências podem devolver extras. Digests não autenticam identidade. As funções continuam sendo de laboratório, com um escritor, reconstruções históricas custosas e baterias pequenas/correlacionadas.

Qualidade factual permanece `NOT_EVALUATED`, aprendizado geral `NOT_ESTABLISHED`; a saída é sempre não qualificada. A próxima investigação é medir a confiabilidade dos retornos e a escolha de evidências em dados novos, sem transformar o avaliador em oráculo ou gravar saídas geradas como fatos. O PR continua em rascunho.
