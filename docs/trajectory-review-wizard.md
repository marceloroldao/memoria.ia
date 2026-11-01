# Assistente de avaliação pelo terminal

`trajectory_review_wizard.py` conduz o ciclo de revisão, decisão, registro explícito e avaliação posterior em português, sem exigir que o operador escreva JSON ou copie IDs de recibos entre comandos. É um lançador local Linux sobre as operações de auditoria já existentes.

## Executar

Se ainda não preparou a biblioteca, use o [preparador do piloto](trajectory-operator-setup.md), que compila em pasta isolada e verifica persistência temporária antes de abrir este assistente.

Com a biblioteca nativa construída conforme `trajectory-feedback-session.md`, execute a partir da raiz do repositório:

```sh
PYTHONPATH=src python scripts/trajectory_review_wizard.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir ./data/avaliacao-operador \
  --scope principal \
  --actor marcelo
```

`--actor` é uma identidade declarada, sem autenticação. `--scope` seleciona a região de memória. Preserve o diretório para continuar após reiniciar.

O menu oferece registrar uma entrada, iniciar revisão, listar decisões, retomar uma decisão, ver entradas, exportar evidências e sair. A opção **[6]** grava um novo JSON fora da pasta de dados, com o histórico e a auditoria do escopo, sem novos eventos; consulte os detalhes e limites no [roteiro do piloto](trajectory-operator-pilot.md#evidência-da-rodada). A listagem de entradas mostra texto literal, sequência e origem declarada. Nas candidatas recuperadas, o assistente mostra sequências de origem e informa separadamente candidatas disponíveis e suspensas por feedback.

## Ciclo guiado

1. Registre as observações iniciais pelo menu, identificando a origem como relato/observação declarada ou conteúdo gerado. Também é possível usar uma memória já preparada pelas operações existentes.
2. Inicie a revisão e informe a pergunta, os conjuntos de exemplos, a origem declarada e os pares de texto de origem/conteúdo associado. As entradas são feitas uma linha por vez.
3. Confira as candidatas, as lacunas e todos os conjuntos oferecidos, inclusive os sem marcação estrutural. A revisão exata é preservada em auditoria, contendo os textos oferecidos, antes da decisão.
4. Escolha um conjunto, adie ou rejeite todos. Informe a justificativa. O assistente registra a decisão e exibe seu ID. Sair sem decidir deixa apenas o recibo de revisão.
5. Se escolheu um conjunto, faça uma ação separada: registrar como observação declarada, registrar como conteúdo gerado ou pular. A escolha do conjunto sozinha não incorpora exemplos. Na origem gerada, ambos os textos do par permanecem excluídos da aprendizagem.
6. Confira a leitura posterior e as contagens brutas, disponíveis e suspensas. Declare ajudou, ficou igual, piorou ou dúvida, com justificativa. Também pode adiar o registro do resultado.

Nenhuma alternativa é selecionada pelo programa por causa de uma marcação estrutural ou de um score. Os conjuntos são mostrados na ordem recebida. Mais candidatas não certificam melhora, e a avaliação declarada continua separada da comparação objetiva. O assistente não autentica proveniência, verifica fatos ou transforma justificativas em aprendizagem.

## Retomar

Liste as decisões e escolha a opção de retomada. Informe o ID exibido e use a mesma identidade declarada. O assistente mostra a revisão original e a leitura atual para conferir mudanças antes de qualquer registro. O resultado posterior continua vinculado à decisão e à revisão originais.

Os IDs das observações incorporadas derivam do ID da decisão, do índice do par e do papel do texto. Repetir uma incorporação na retomada, com os mesmos textos e origem, devolve reenvios idempotentes. Não duplica as observações. A retomada não permite reclassificar os mesmos registros de gerado para observação de usuário.

Interromper depois de registrar a decisão, inclusive por fim da entrada do terminal, preserva uma decisão retomável. Um resultado posterior é um novo evento e recebe novo ID. Uma decisão não é apagada ao adiar a avaliação.

Na retomada de um lote parcialmente registrado, os registros existentes precisam formar um prefixo contínuo, na ordem prevista, no final da região local. Uma observação intercalada, um trecho fora de ordem ou contexto posterior ao trecho incompleto faz a incorporação ser recusada antes de novos pares. Confira o histórico: o assistente não reordena ou apaga observações para reconstruir a sequência. Um lote já completo pode ser reenviado depois de contexto posterior, sem acrescentar observações.

## Limites e falhas

O assistente usa os mesmos limites da sessão. As linhas de entrada inicial têm até 2000 caracteres; consultas até 4000; conjuntos de exemplos seguem os limites já documentados em `trajectory-demonstration-review.md`.

Antes de começar a incorporação, confere **o conjunto inteiro**, incluindo barreiras geradas, contra 64 observações e 4096 caracteres no escopo. Confere também conflitos com IDs previamente registrados. Se esse preparo falhar, nenhum novo par do conjunto é gravado. A decisão e seu recibo permanecem na auditoria.

A incorporação é uma sequência de operações nativas explícitas, cada uma com flush. Não é uma transação de lote: falha de armazenamento ou interrupção durante o registro pode deixar uma parte confirmada. Confira o histórico e retome a mesma decisão para reutilizar os IDs, em vez de iniciar outra incorporação com IDs diferentes. Falhas de armazenamento encerram o lançador; não há rollback automático.

Textos exibidos são representados literalmente, com controles escapados, e não interpretados como comandos ou formatação de terminal. A aplicação mantém o lock exclusivo de escritor do diretório enquanto está aberta.

## Validação

O avaliador usa o mesmo controlador interativo com respostas programadas sobre armazenamento nativo real. São **oito percursos** nos catálogos de pressão e potência: escolher demonstração, escolher contraste, adiar e rejeitar todos. As transcrições identificam entradas como `scripted_input`. Isso testa o protocolo e a persistência, não a capacidade de uma pessoa de decidir corretamente.

Os testes adicionais verificam origem gerada, registro explicitamente pulado, retomada após reinício sem duplicação, recusa de reclassificar origem, limite de lote sem escrita parcial por falha de preparo, fim de entrada após a decisão, identidade declarada diferente e dois percursos em subprocesso real: registrar/listar entradas e concluir revisão/decisão/resultado sem JSON manual.

Relatório: `benchmark-results/trajectory-review-wizard.json`. SHA-256 canônico sem o próprio campo de hash: `f57c790fe74c61bd3b1bda8f558cd97f762f2142e58060c72263528e8ae9c7ba`.

Passaram **45 testes locais**, doze novos e 33 regressões dos diários de decisão e resultado. Passaram **72/72 verificações** nos oito percursos programados, com igualdade de auditoria e aprendizagem após reabertura. O relatório repetiu byte a byte; o relatório anterior de resultados também reproduziu integralmente sem alterações. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

```sh
PYTHONPATH=src python scripts/trajectory_review_wizard_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --output /tmp/review-wizard.json

PYTHONPATH=src MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
  python -m pytest -q tests/test_trajectory_review_wizard.py
```

As operações anteriores, os diários, o motor e a ABI permanecem preservados. `human_evaluation_status=NOT_PERFORMED` e `general_learning_status=NOT_ESTABLISHED` continuam explícitos. A próxima etapa é realizar percursos com um operador real e dados de origem conhecida, usando os registros para identificar dúvidas, falhas e efeitos observados.

O roteiro para essa rodada está em [trajectory-operator-pilot.md](trajectory-operator-pilot.md), junto da validação cumulativa e da correção de retomada com histórico parcial intercalado.
