# Molduras aprendidas para discriminar informação solicitada

Esta etapa reaproveita `learn_frames`, de `trajectory_analogy_frame_probe.py`, em um leitor opcional de escopo explícito. A consulta pode ser nova: não precisa já ter sido gravada para existir uma hipótese. Nenhum vocabulário de atributos, classificador de perguntas ou resposta do avaliador é passado ao leitor.

As molduras continuam restritas: três variáveis distintas copiadas entre perguntas e conteúdos adjacentes, prefixos/sufixos constantes e uma ponte constante no destino. O algoritmo de aprendizagem é fornecido pelo programador. Os exemplos são textos sintéticos curados, não descobertas autônomas ou avaliação cega de compreensão.

## Implementação

`AttributeFrameReader(rows, region).read(query)` recebe somente cinco campos por observação: `hierarchy_id`, `source_id`, `sequence`, `text`, `source_kind`. A projeção filtra o escopo **antes** de aprender, exclui conteúdo gerado como evidência e conserva suas barreiras de sequência. Metadados de referência e vínculos explícitos `reply_to` não entram na aprendizagem.

O leitor exige encaixe da pergunta inteira na moldura. Só devolve payloads completos já observados no mesmo escopo, com todos os seus endereços aceitos, identificadores das molduras e pares de ocorrências adjacentes que sustentam cada demonstração. Não gera um fato a partir de um fragmento. Duplicatas mantêm origens, mas não escolhem um vencedor por maioria. Mais de uma candidata implica abstenção da proposta única.

A projeção é limitada a **64 linhas e 4096 caracteres** por escopo; excesso é recusado integralmente. Cada leitura verifica que snapshot e estado de aprendizagem permanecem iguais. A resposta é uma cópia independente, para que alterações feitas pelo chamador não contaminem consultas seguintes. Esse leitor é uma projeção em Python dos registros nativos; não substitui o core nem representa pesos cognitivos novos persistidos.

## API local opcional

O MVP Linux existente admite o campo `attribute_frames:true` em `POST /api/query`:

```json
{"scope":"principal","text":"Qual nome do meu gato?","attribute_frames":true}
```

Os candidatos originais continuam em `candidates`, sem alteração. O campo adicional `attribute_frames` mostra os candidatos por molduras, seus testemunhos, `proposal_payload_id` e a razão da proposta/abstenção. Sem a opção, o envelope anterior permanece idêntico. A opção é independente de `experimental:true`, que continua usando a rota experimental anterior.

Para ensinar, registre pelo fluxo normal exemplos como pergunta sobre barco → nome do barco, pergunta sobre avião → nome do avião, pergunta sobre drone → nome do drone. Use episódios separados: nos testes, cada par de turnos do usuário termina com uma barreira `assistant_generated`, que delimita a sequência e não fornece evidência. Depois registre o nome do gato. A pergunta sobre o gato pode recuperar esse conteúdo sem ter sido ensinada literalmente. Exemplos completos estão em `demonstrations()` no script; eles não são carregados automaticamente na memória do usuário.

Nenhum resultado é factual: continuam `answer:null`, `qualified:false`, `selection_used:false` e `query_recorded:false`. `absence_proven:false` é explícito: não encontrar candidata não prova que a informação inexista. O status e os candidatos da recuperação original podem continuar presentes mesmo quando a rota por molduras se abstém. A UI não foi modificada para escolher uma rota; essa opção está disponível na API local autenticada.

O limite experimental é verificado antes da análise; as consultas comuns continuam disponíveis acima dele. O mesmo lock e a verificação de snapshot do MVP envolvem a rota nova. Testes por HTTP real com término e reinício preservam o envelope anterior, origens e histórico completo.

## Comparação reproduzível

Reutilizamos as 37 perguntas do diagnóstico anterior, com referências exclusivas do avaliador. Acrescentamos 30 pares de demonstração em dez molduras, ensinados em cinco escopos. Sujeitos das demonstrações são barco, avião e drone; as perguntas avaliadas usam outros sujeitos. Perguntas avaliadas não são gravadas pela consulta; a exceção de conteúdo exato já fazia parte do catálogo original.

| Observações | Rota | Conjuntos exatos | Conteúdos esperados recuperados | Extras | Perdidos |
| --- | --- | ---: | ---: | ---: | ---: |
| Catálogo original | Recuperação nativa | 13/37 | 28 | 51 | 0 |
| Catálogo original | Molduras sem demonstrações | 16/37 | 0 | 0 | 28 |
| Catálogo + demonstrações | Recuperação nativa | 3/37 | 28 | 193 | 0 |
| Catálogo + demonstrações | Molduras aprendidas | 30/37 | 16 | 0 | 12 |

A comparação entre as duas últimas linhas usa exatamente as mesmas observações. As demonstrações também viram conteúdo recuperável na busca ampla, aumentando seus extras. Não se deve atribuir a diferença 13→30 somente a um filtro sobre o catálogo original: houve ensino explícito. Os 16 conjuntos exatos sem demonstrações são controles cujo esperado era vazio; abstendo-se de tudo, o leitor perdeu todos os 28 conteúdos positivos.

Nos dez controles de atributo ausente, a rota ensinada não retorna candidatas. Na pergunta sobre nome do gato, retorna os dois nomes e suas origens, sem o trecho sobre onde ele dorme; na pergunta sobre onde dorme, retorna esse trecho. Isso demonstra transferência limitada das molduras observadas, não compreensão geral da língua.

As sete falhas ficam preservadas: paráfrase do nome do gato, caixa alta, conteúdo exato consultado como texto, paráfrase da cor do Corsa, cor do céu e duas consultas de estado do robô. Totalizam 12 conteúdos perdidos. A moldura de estado conserva inclusive um sufixo comum dos exemplos ensinados que não serve para online/offline: uma generalização estrutural pode restringir demais a resposta. Não ajustamos os exemplos para eliminar essas falhas após observá-las.

## Contraexemplos

- **Ensino enganoso:** exemplos ligando pergunta de nome a frases de cor fazem a rota propor cor para uma pergunta de nome. A hipótese permanece sem qualificação.
- **Ensino contraditório:** misturar demonstrações incompatíveis pode aprender uma moldura ampla demais e recuperar também o hábito do gato. Esse extra é uma falha esperada no teste, não uma aprovação semântica.
- **Conflitos repetidos:** vinte cópias de um nome não eliminam o nome rival nem autorizam uma proposta única.
- **Sem suporte:** exemplos repetidos de um único sujeito não substituem três variáveis distintas. Demonstrações estrangeiras ou com uma resposta gerada não suprem o ensino local ausente.
- **Renomeação opaca:** um teste bijetivo de símbolos na projeção conserva a transferência, sem reconhecimento de palavras. Não é um teste multimodal nem valida a tokenização nativa desses símbolos renomeados.

## Verificação

Relatório completo: `benchmark-results/trajectory-attribute-frame.json.gz`. A execução usa o BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`, mede ambas as rotas, conserva fontes e testemunhos e verifica 14 controles de integridade, incluindo leitura sem escrita, reabertura fria e saída completa repetida. Duas execuções em processos separados reproduziram o relatório byte a byte.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_attribute_frame_probe.py \
  tests/test_trajectory_analogy_frame_probe.py tests/test_trajectory_native_evidence_join_probe.py \
  tests/test_trajectory_local_mvp.py tests/test_trajectory_local_mvp_variation.py

PYTHONPATH=src python scripts/trajectory_attribute_frame_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --output /tmp/attribute-frame.json

# Deve encerrar com código 1: falhas de qualidade continuam presentes.
PYTHONPATH=src python scripts/trajectory_attribute_frame_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so --strict-quality
```

Passaram **52 testes locais**, incluindo 22 novos casos do leitor/API e 30 anteriores. O gate tem `integrity_status:PASS`, mas conserva `retrieval_quality_status:FAIL_EXTRA_OR_MISSING_CONTENT` e `factual_quality_status:NOT_EVALUATED`. CI verde verifica esses contratos e a reprodução dos resultados, sem aprovar qualidade factual. PR continua em rascunho, sem alteração do servidor publicado ou integração OFF.IA.

Próxima investigação: variar redação e flexão em um conjunto separado, mantendo controles de atributos ausentes e exemplos enganosos. Qualquer ganho de cobertura precisa medir os extras reintroduzidos; falta de testemunho continuará sem equivaler a prova de ausência.
