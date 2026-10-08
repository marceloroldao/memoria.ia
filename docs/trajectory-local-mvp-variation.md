# MVP local: perguntas variadas e limites da recuperação

Continuação de `ca7f2b4`. Os oito workflows aplicáveis desse commit passaram, incluindo trajetória `37665600934`; a regressão experimental condicional foi pulada. Esta etapa amplia o diagnóstico e melhora a transparência da consulta, sem mudar o motor, a ingestão, o ranking nativo ou a escolha experimental de raízes. O PR #374 continua em rascunho.

## O que mudou no produto experimental

Cada candidato apresenta os valores já calculados pelo runtime (`score`, `exact_overlap`, `surface_overlap`, `association_mass`) em `native_support`, sempre com `support_is_factual_confidence:false`. São medidas de recuperação, não probabilidades de verdade, pertinência ou resposta correta. Na tela, conteúdo idêntico à consulta é identificado como conteúdo exato já registrado; os demais trechos vêm com o aviso para conferir se respondem à pergunta.

A API também informa quantos contextos nativos retornaram. Ao atingir 16 contextos, a tela avisa que outras alternativas podem estar ausentes: `limit_may_have_hidden_alternatives:true`. Esse sinal não afirma que houve truncamento em todo caso; o runtime atual não informa o total antes do limite. `all_relevant_content_recovered:null` conserva a ausência de certificação de cobertura, mesmo com poucos candidatos. O teste de vinte nomes diferentes demonstra concretamente que quatro alternativas ficam fora dos dezesseis resultados.

Textos, endereços aceitos, exclusão de fontes geradas, separação de campos nativos e abstenções experimentais permanecem intactos. Consultas continuam sem registro/retroalimentação e com `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`. O MVP apresenta evidências; não produz respostas factuais.

## Bateria de recuperação

`scripts/trajectory_local_mvp_variation_gate.py` grava 25 entradas sintéticas em regiões de animais, carros, casa, agenda, dispositivos e controles de escopo. Algumas entradas se repetem, algumas concorrem, e três são geradas por assistente. Executa 37 consultas, repete-as sem aprendizado e depois reinicia o processo e compara a saída completa. A API recebe somente escopo, texto e origem para gravar, ou escopo/texto para consultar. Categorias e conjuntos esperados são exclusivos do avaliador.

| Categoria do avaliador | Consultas | Conjuntos exatos | Conteúdos esperados recuperados | Conteúdos extras | Conteúdos perdidos |
| --- | ---: | ---: | ---: | ---: | ---: |
| Informação positiva | 13 | 6 | 13 | 9 | 0 |
| Informações concorrentes | 7 | 4 | 14 | 4 | 0 |
| Atributo não informado | 10 | 0 | 0 | 23 | 0 |
| Entidade não informada | 2 | 0 | 0 | 8 | 0 |
| Conteúdo exato observado | 1 | 0 | 1 | 3 | 0 |
| Consulta relacionada a conteúdo de outro escopo | 1 | 0 | 0 | 4 | 0 |
| Escopo vazio | 1 | 1 | 0 | 0 | 0 |
| Escopo somente gerado | 1 | 1 | 0 | 0 | 0 |
| Sem sobreposição | 1 | 1 | 0 | 0 | 0 |
| Total | 37 | 13 | 28 | 51 | 0 |

Todos os 28 conteúdos de referência por consulta estão entre os candidatos, mas aparecem 51 conteúdos extras. São 24 consultas com excesso, e somente 13 conjuntos exatos. As perguntas correlacionadas e as referências por consulta não são amostras independentes; este total não estima precisão geral ou qualidade factual. Não substitui o relatório anterior de sete casos, que continua 5/7 com suas falhas preservadas.

Exemplos de falha: perguntar amperagem recupera o trecho que informa volts; perguntar endereço recupera a cor da casa; perguntar cor/idade do gato recupera nomes e hábitos. A recuperação reconhece conteúdo associado ao assunto, mas não estabelece que o atributo pedido tenha sido observado. Nos dez controles de atributo ausente, nunca retornou uma lista vazia. Uma consulta sobre o nome registrado somente no escopo estrangeiro recupera outros nomes locais: **não houve vazamento da origem estrangeira**, e a irrelevância dos conteúdos locais continua como falha distinta.

## Por que não instalar um limiar de score

O diagnóstico separado `threshold_shadow` enumera os 71 estados diferentes produzidos por um único limiar global sobre os scores dos candidatos. Usa fronteiras imediatamente superiores a cada score observado e a regra `score >= limiar`, sem alterar API, memória ou ranking. Todos os estados ficam no relatório; nenhum limiar é instalado ou apresentado como calibrado.

- Mantendo os 28 conteúdos de referência, o melhor estado deste conjunto ainda traz **39 extras**.
- Sem nenhum extra, o estado que mais conserva referência recupera **1/28** conteúdos e perde os outros 27.
- Nenhum estado produz os 37 conjuntos exatos.

Por exemplo, o trecho de volts recuperado para uma pergunta de amperagem tem score aproximado de 0,9104, maior que os dois nomes corretos na consulta de nome do gato (0,9026/0,8992). Um score alto não determina qual atributo o usuário solicitou. A varredura usa as próprias referências desta amostra; seus melhores estados não são parâmetros aprendidos nem desempenho em dados reservados. Essa conclusão vale para este corte escalar global e este catálogo, não para toda política de recuperação possível.

## Verificação

**12/12 controles agregados de integridade**, cobrindo todas as 37 consultas: histórico de todos os escopos inalterado; igualdade da saída completa em repetição e reabertura fria; ausência de reforço por consultas; envelope sem qualificação; origem observada com texto correspondente; todas as ocorrências aceitas de cada payload retornado; exclusão de gerados; escopo e scores sem promoção a confiança factual. O relatório normaliza endereços aleatórios em sequências de origem para reprodução; a comparação fria usa as saídas completas com seus UUIDs reais.

**26 testes locais passaram**, com sete novos contratos: duas verificações da API (diagnósticos/limite) e cinco do avaliador (referências isoladas, origens inválidas, catálogo, varredura sem seleção e HTTP real). O relatório completo reproduziu byte a byte. O gate anterior continua 12/12 de integridade e 5/7 conjuntos exatos, também com reprodução byte a byte. Um teste JSDOM contra HTTP real passou com registro, rótulos de conteúdo exato/associado, fontes, texto HTML seguro, aviso para vinte alternativas com dezesseis cards e remoção do aviso ao mudar para memória vazia; nenhum erro de script. Isso não verifica renderização visual. Compilação Python/JavaScript e `git diff --check` completam os checks locais. Após publicação de `a859b7c`, os oito workflows aplicáveis passaram, incluindo trajetória `37730431571`; a regressão experimental condicional foi pulada.

O gate conserva `FAIL_EXTRA_OR_MISSING_CONTENT` e qualidade factual `NOT_EVALUATED`. Sem modo estrito, retorna sucesso apenas pela integridade; `--strict-quality` retorna **1** pelas falhas semânticas preservadas. CI verde não equivale a aprovação semântica. Não se acrescentou vocabulário, classificador de pergunta, resposta de referência ou política de votação ao motor.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
MEMORIA_NATIVE_LIB=build/trajectory-native/libmemoria_mobile.so \
PYTHONPATH=src python -m pytest -q \
  tests/test_trajectory_local_mvp.py tests/test_trajectory_local_mvp_variation.py \
  tests/test_native_structural_text_adapter.py tests/test_product_structural_observation.py \
  tests/test_product_webui.py

PYTHONPATH=src python scripts/trajectory_local_mvp_variation_gate.py \
  --library build/trajectory-native/libmemoria_mobile.so

# Diagnóstico de qualidade: este conjunto deve retornar 1.
PYTHONPATH=src python scripts/trajectory_local_mvp_variation_gate.py \
  --library build/trajectory-native/libmemoria_mobile.so --strict-quality
```

Relatório: `benchmark-results/trajectory-local-mvp-variation.json`. Para executar a tela, use `docs/trajectory-local-mvp.md`. Mantêm-se as pendências de conferência visual em navegador, integração com o servidor publicado e distribuição remota.

## Próxima investigação

Testar se demonstrações brutas observadas de pergunta/conteúdo permitem aprender relações que discriminem o tipo de informação solicitado, com consultas novas e atributos não informados como controles. A seleção não deve receber a resposta do avaliador, deduzir fatos inexistentes nem reforçar suas próprias consultas. As molduras experimentais e suas falhas históricas continuam como referência; melhorar o assunto recuperado não basta para validar uma resposta.
