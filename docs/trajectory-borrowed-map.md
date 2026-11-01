# Reaproveitar mapas entre escritas: hipóteses e contraexemplo

**Duas demonstrações permitem recuperar 16/16 conteúdos quando o mapa é compartilhado. Com as mesmas observações, uma hipótese alternativa de mapa torna as mesmas 16 recuperações incorretas para essa referência. O reaproveitamento não foi promovido a seleção ou ao leitor padrão.**

## Protótipo isolado

`trajectory_borrowed_map.py` oferece uma leitura experimental, sem escrita, separada de `FeedbackSession`, do assistente e do leitor padrão. Usa uma moldura doadora aprendida pelo algoritmo existente com três testemunhos distintos. Duas demonstrações de uma nova escrita precisam ter variáveis distintas e destinos observados compatíveis com esse mapa e formato de conteúdo.

Quando uma consulta da nova escrita usa um símbolo ausente dessas duas demonstrações, o protótipo pode tomar emprestado o par testemunhado na moldura doadora. Retorna somente payloads já observados no escopo e admissíveis pela origem. Não cria textos de resposta. As hipóteses carregam o ID da moldura doadora, endereços dos três testemunhos doadores, endereços dos dois exemplos da nova escrita e os pares tomados emprestados.

Cada rota é marcada `UNWITNESSED_IN_NEW_SOURCE_FORM`. O fato de o mapa estar testemunhado em outra escrita não o torna testemunhado nesta. `answer=null`, `qualified=false`, `selection_used=false` e `learning_performed=false` permanecem explícitos, mesmo com uma única hipótese. Nenhum score ou gabarito participa da leitura.

Um par observado da nova escrita que contradiga o mapa doador veta essa rota. O protótipo não pode ignorar esse contraexemplo escolhendo apenas dois exemplos convenientes. Esse veto é conservador: conflitos ou observações inadequadas podem suspender uma hipótese, sem estabelecer qual conteúdo é verdadeiro. O histórico original continua intacto.

## Experimento e limite de identificação

São reutilizados os mapas e contextos sintéticos da [avaliação de novas escritas](trajectory-surface-evaluation.md). As duas âncoras da nova escrita cobrem os três símbolos antigos, sem incluir o quarto símbolo necessário às consultas-alvo. As entidades-alvo e suas perguntas ficam fora dessas âncoras. Os fatos-alvo, incluindo alternativas, já estão registrados.

Para cada condição são construídos dois cenários com **as mesmas observações, as mesmas consultas e as mesmas identidades de evento**:

| Cenário sintético | Regra ainda não observada para o quarto símbolo na nova escrita |
|---|---|
| Mapa compartilhado | Igual ao mapa da escrita original |
| Mapa diferente | Outro destino injetivo, também com conteúdo já observado |

Somente a referência do avaliador muda entre cenários. Ela representa duas funções de transformação compatíveis com os exemplos oferecidos, não duas verdades verificadas do mundo real. O leitor não recebe essa referência nem a identidade do cenário. Há verificação explícita de que o hash das observações e as hipóteses são idênticos nos dois cenários.

Isso expõe o limite: exemplos que não incluem o quarto símbolo não determinam se seu mapa será compartilhado. A suposição pode ajudar numa família e falhar em outra sem que a evidência apresentada permita decidir entre elas. Não é uma estimativa de frequência de erros em conversas reais.

## Resultados positivos e negativos

| Condição | Mapa compartilhado | Mapa diferente | Ausência em cada cenário |
|---|---:|---:|---:|
| Sem âncoras | 0/16 | 0/16 | 40/40 |
| Uma âncora | 0/16 | 0/16 | 40/40 |
| Duas âncoras adequadas | **16/16** | **0/16** | 40/40 |
| Âncora incompatível | 0/16 | 0/16 | 40/40 |
| Âncoras geradas | 0/16 | 0/16 | 40/40 |
| Âncoras em outro escopo | 0/16 | 0/16 | 40/40 |

Com duas âncoras no cenário de mapa diferente, cada consulta tem uma hipótese extra e um conteúdo esperado ausente: **16 extras e 16 ausências**. Não se trata apenas de abstenção. O leitor padrão permanece sem candidatas para as consultas de nova escrita avaliadas; o protótipo é uma via adicional e isolada de hipóteses.

Foram **672 consultas em 96 memórias novas**, formando 48 pares de cenários indistinguíveis. São duas sementes, dois domínios, duas escritas, seis condições e dois cenários. As repetições pareadas e os domínios correlacionados não são amostras independentes para calcular precisão geral.

Passaram **768 controles de integridade**, incluindo histórico e escopo estrangeiro preservados, consultas não incorporadas, nenhuma seleção, reabertura nativa, igualdade das hipóteses após reiniciar, candidatas do leitor padrão preservadas e os dois controles de indistinguibilidade por par de cenários.

## Validação e reprodução

Passaram **32 testes**, quatorze novos do protótipo e de seu avaliador e dezoito regressões de superfície/transferência. Cobrem separação dos alvos, mundos com entradas idênticas, contraexemplo nos dois tipos de escrita, proveniência doadora e das âncoras, exclusão de origens geradas e estrangeiras, âncora repetida, consulta com duas pistas, conteúdo-alvo gerado e veto por testemunho contraditório.

```sh
PYTHONPATH=src python scripts/trajectory_borrowed_map_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/borrowed-map.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_borrowed_map.py
```

O workflow mede integridade e conserva o contraexemplo. Seu sucesso não aprova a hipótese como resposta factual. Relatórios: `benchmark-results/trajectory-borrowed-map.json` e `benchmark-results/trajectory-borrowed-map-validation.json`.

O relatório repetiu byte a byte após o veto de testemunho contraditório. Compilação Python e `git diff --check` passaram. A CI da etapa anterior, commit `d68c379d`, concluiu com sucesso na execução `41279129515`; a CI deste incremento fica pendente após publicação.

Este é um experimento posterior ao diagnóstico, com dados curados e leitor Python sobre persistência nativa BDR. Não altera a ABI, a sessão, o assistente ou o serviço de produção. A avaliação humana e a aprendizagem geral seguem não estabelecidas. A próxima direção é obter testemunho do par faltante antes de promover sua aplicação, mantendo explícita a diferença entre hipótese e relação observada.
