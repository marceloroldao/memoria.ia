# Transferência para consultas não demonstradas

**Recuperação na moldura ensinada: 8/8 após demonstração adicional, contra 0/8 nos três controles. Mudança de caixa e paráfrase: 0/8 mesmo depois da demonstração. O conjunto completo continua reprovado.**

Este incremento avalia o leitor experimental já existente, sem modificar o motor, o armazenamento ou a ABI. A execução combina persistência nativa em BDR com o leitor de molduras em Python usado pela sessão. Não demonstra que a inferência inteira roda dentro da biblioteca nativa, nem integração ao OFF.IA ou servidor.

## Método fixado antes da execução

Dois domínios sintéticos, umidade e vibração, usam identificadores fictícios de três símbolos. As sementes `20261101` e `20261102` sorteiam símbolos e mapas injetivos arbitrários para outros símbolos, sem conversão automática para minúsculas. Cada mapa é reutilizado nos dois domínios; esses domínios não são amostras estatísticas independentes. São quatro contextos, cada um testado em quatro memórias novas e separadas.

Cada contexto começa com três demonstrações pergunta/conteúdo para três símbolos conhecidos. Dois fatos-alvo com valores distintos são registrados isoladamente, sem suas perguntas. As consultas de avaliação combinam esses símbolos com um quarto símbolo cujo mapa ainda não foi demonstrado. Todas as perguntas de avaliação ficam ausentes das observações, antes e depois da intervenção.

As quatro condições são executadas sempre, sem consultar o score para escolher a seguinte:

| Condição | Observação adicional |
|---|---|
| Baseline | Nenhuma |
| Irrelevante | Relato sem demonstração |
| Contraste | Um par que demonstra um mapa incorreto para o quarto símbolo |
| Intervenção | Um par que demonstra o mapa previsto para o quarto símbolo |

O par adicional usa outra composição de entidade e outro valor. Não inclui nenhuma das perguntas ou dos fatos-alvo. Os rótulos esperados existem somente no avaliador e no relatório, sem entrar nos comandos da sessão. O avaliador não reinjeta consultas ou saídas no aprendizado.

Cada memória recebe nove consultas: duas novas combinações na moldura original, mudança de caixa e paráfrase de uma delas e cinco controles de ausência. Os controles cobrem atributo ausente, entidade ausente, símbolo sem mapa, conteúdo somente gerado e conteúdo efetivamente registrado em outro escopo.

Pontuação exata exige igualdade entre o conjunto de candidatas disponíveis e o conjunto esperado, sem fragmentos extras. Recuperar uma candidata não conta como responder: `answer=null`, `qualified=false` e `selection_used=false` permanecem explícitos. Os fatos-alvo já foram observados; a novidade é a consulta e sua associação, não a descoberta de um valor nunca apresentado.

## Resultados, incluindo falhas

| Condição | Novas combinações | Caixa/paráfrase | Controles de ausência |
|---|---:|---:|---:|
| Baseline | 0/8 | 0/8 | 20/20 |
| Irrelevante | 0/8 | 0/8 | 20/20 |
| Contraste | 0/8 | 0/8 | 20/20 |
| Intervenção | **8/8** | **0/8** | **20/20** |

Foram **144 consultas em 16 memórias**. Depois da intervenção, as quatro mudanças de caixa e as quatro paráfrases permaneceram sem o conteúdo esperado. Essa falha impede interpretar o resultado como compreensão flexível de linguagem. As condições de controle não melhoraram as novas combinações. Não houve seleção de resposta factual em nenhuma consulta.

O subconjunto predefinido de moldura original e controles passa em 28/28, mas o conjunto completo da intervenção passa em 28/36. Por isso o relatório mantém `retrieval_status=EXTRA_OR_MISSING_CONTENT`. O resultado sustenta transferência restrita de mapas de símbolos nos cenários construídos, sem provar aprendizagem geral, validade das observações do mundo real ou precisão fora dessas molduras.

## Integridade e reprodução

Passaram **112 verificações** de leitura sem mudança, escopo estrangeiro preservado, repetição de respostas completas, candidatas somente de observações admitidas, nenhuma qualificação factual e igualdade de histórico e leituras após reabertura. Esses controles medem integridade, separadamente da recuperação. Passaram **32 testes**, sete novos do avaliador e 25 regressões de revisão/sessão. Os testes conferem separação dos alvos, comandos sem gabarito, ausência de reinserção e recusa do modo estrito quando a integridade passa mas a recuperação falha.

```sh
PYTHONPATH=src python scripts/trajectory_transfer_evaluation.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/transfer-evaluation.json

PYTHONPATH=src python scripts/trajectory_transfer_evaluation.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/transfer-evaluation-strict.json --strict-retrieval
```

O primeiro comando retorna zero se os controles de integridade passarem, conservando as falhas de recuperação no relatório. O segundo retorna **1** nesta execução, porque inclui as falhas de caixa/paráfrase no gate completo. Sucesso do workflow não certifica qualidade de recuperação.

O relatório `benchmark-results/trajectory-transfer-evaluation.json` guarda observações, consultas, referências, candidatas com proveniência, hashes das leituras completas e todos os scores. O relatório de validação complementar guarda a identidade do binário, hashes das fontes e resultados dos testes. Não é um benchmark independente ou cego: são duas sementes em molduras correlacionadas, concebidas a partir do diagnóstico anterior. Não houve avaliação humana, mudanças no motor, medição de escala ou validação multimodal.

A próxima investigação deve explicar por que pequenas mudanças na superfície da pergunta perdem a moldura, sem substituir o problema por regras específicas de domínio. As falhas registradas são a baseline para essa investigação. A rodada humana do piloto continua pendente em paralelo.
