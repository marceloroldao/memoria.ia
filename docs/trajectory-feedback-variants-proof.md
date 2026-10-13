# Aprender molduras observadas de perguntas: ablação controlada

O leitor e a sessão permanecem intactos. Esta etapa acrescenta somente um avaliador com demonstrações brutas observadas. Compara quatro memórias separadas: baseline, exemplos em maiúsculas, exemplos de paráfrase e ambos. Cada variante contém três demonstrações de pergunta/conteúdo com as entidades de treinamento. Nenhuma pergunta-alvo ou conteúdo-alvo é acrescentado por esses exemplos.

Cada braço consulta quatro domínios e oito perguntas por domínio. Dois catálogos, development e reserved, totalizam **256 consultas**. O reservado troca entidades e valores das demonstrações e dos alvos, preservando as famílias de molduras. Ele testa transferência para outras entidades dentro dessas molduras; não testa paráfrases livres ou famílias de frases não ensinadas. Os catálogos são pequenos, curados e correlacionados. Não houve operador humano ou ajuste do leitor entre os resultados.

## Efeito por tipo de demonstração

Cada célula mostra conteúdos esperados recuperados entre oito referências por tipo de pergunta, não respostas factuais corretas. Não há seleção entre informações concorrentes.

| Catálogo e memória | Moldura original | Paráfrase | Maiúsculas | Extras em qualquer consulta |
|---|---:|---:|---:|---:|
| Development: baseline | 6/8 | 0/8 | 0/8 | 0 |
| Development: ensinar maiúsculas | 6/8 | 0/8 | 0/8 | 0 |
| Development: ensinar paráfrase | 6/8 | 6/8 | 0/8 | 0 |
| Development: ensinar ambas | 6/8 | 6/8 | 0/8 | 0 |
| Reserved: baseline | 7/8 | 0/8 | 0/8 | 0 |
| Reserved: ensinar maiúsculas | 7/8 | 0/8 | 1/8 | 0 |
| Reserved: ensinar paráfrase | 7/8 | 7/8 | 0/8 | 0 |
| Reserved: ensinar ambas | 7/8 | 7/8 | 1/8 | 0 |

A paráfrase demonstrada passa de 0/8 para 6/8 no primeiro catálogo e para 7/8 no reservado. A moldura original mantém exatamente sua cobertura. Os controles de atributo ausente, entidade ausente, conteúdo somente gerado, conteúdo de outro escopo e ausência de sobreposição retornam listas vazias nos quatro braços dos dois catálogos: **160 consultas negativas**, sem extras.

Isso sustenta um efeito limitado: relações observadas de pergunta/conteúdo permitem transportar a mesma moldura de paráfrase para entidades novas nesta amostra. Não estabelece compreensão semântica geral ou de paráfrases inéditas. As ausências anteriores permanecem: mesmo com a moldura ensinada, nem todos os conteúdos concorrentes são recuperados.

Maiúsculas continuam frágeis: zero recuperações no development e uma no reserved. A origem dessa diferença não foi isolada neste incremento. Não se instalou `.lower()`, normalizador ou conversão global de símbolos para melhorar artificialmente o relatório.

## Integridade

Passaram **112/112 verificações por catálogo, 224 no total**: leitura sem escrita, repetição completa, histórico sem feedback implícito, conteúdo de origem aceita no escopo, envelopes sem qualificação e igualdade de histórias e consultas após fechar/reabrir o handle. As saídas completas, observações, referências de pontuação e scores de cada braço constam dos relatórios. As referências entram somente depois da leitura, na função de pontuação.

O baseline de development mantém os scores anteriores: 6 conteúdos recuperados, 18 ausentes e nenhum extra nas 32 consultas. O relatório anterior `trajectory-feedback-portuguese.json` permanece preservado. Esta etapa não muda o MVP, a ABI, os leitores ou a política de feedback.

Validação local: **18 testes passaram** (seis da ablação e doze regressões da sessão e da bateria em português). Os dois relatórios foram repetidos e coincidiram byte a byte. Todas as **32 saídas completas e scores** do braço baseline foram comparadas com o relatório anterior e permaneceram idênticas. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

| Relatório | Hash do conteúdo canônico sem o próprio campo de hash |
|---|---|
| `trajectory-feedback-variants-development.json` | `54f8f153602fcca87beb60bc9b4f62589d67ffdd9bd8263bd10b5378fa02cd8b` |
| `trajectory-feedback-variants-reserved.json` | `cb6da7af8c4605e9ff34b153a6561680c26fd00c01282f85826d26c0e9fb9473` |

```sh
PYTHONPATH=src python scripts/trajectory_feedback_variants_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --split reserved --output /tmp/feedback-variants-reserved.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_feedback_variants_probe.py
```

O gate retorna sucesso pela integridade. Cobertura incompleta, `human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` permanecem explícitos. BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

## Próxima investigação

Isolar o problema de maiúsculas: distinguir mudança de escrita na moldura fixa, na entidade copiada e em ambas, incluindo entidades cujos símbolos têm ou não testemunhos observados de transformação. Testar controles de escrita literalmente distinta e campos sensíveis a maiúsculas, antes de propor qualquer equivalência automática. A avaliação humana e a generalização para famílias de perguntas não ensinadas continuam pendentes.
