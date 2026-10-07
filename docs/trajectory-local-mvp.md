# Memoria.ia: MVP local de registro e consulta

Continuação do experimento `50454f4`, mudando a prioridade para um fluxo utilizável: registrar conteúdo, consultar, inspecionar origens e voltar após um reinício. O PR #374 continua em rascunho. Este é um lançador opcional do repositório, separado do servidor de produto publicado; o núcleo, os seletores padrão e a ABI nativa permanecem intactos.

## Executar em Linux

É preciso Python 3.10+, CMake, compilador C e a biblioteca nativa com o BDR durável. No checkout deste PR, instale as dependências de produto/teste:

```sh
python -m pip install -e '.[product,test]'
```

Se ainda não tiver a biblioteca construída, use o mesmo BDR fixado da CI:

```sh
git clone https://github.com/marceloroldao/resolutive-DB.git deps/resolutive-DB
git -C deps/resolutive-DB checkout 317882a00f041fc1568ff986af8016b09453f21a
cmake -S native/mobile -B build/trajectory-native -DCMAKE_BUILD_TYPE=Release -DMEMORIA_BDR_ROOT="$PWD/deps/resolutive-DB"
cmake --build build/trajectory-native --target memoria_mobile --parallel 2
```

Escolha uma chave, mantenha o mesmo diretório para reabrir suas entradas e execute:

```sh
export MEMORIA_API_KEY='substitua-por-sua-chave-local'
PYTHONPATH=src python scripts/trajectory_local_mvp.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --data-dir ./data/local-mvp \
  --port 8787
```

Abra `http://127.0.0.1:8787` no computador que executa o servidor. Digite a chave na tela, escolha um nome de memória e registre uma entrada. Consulte depois usando o segundo formulário. A chave não é armazenada no navegador, colocada na URL ou impressa pelo lançador. Para reiniciar, pare com Ctrl+C e execute novamente usando o mesmo diretório. Este comando não publica a aplicação nem permite acesso remoto.

Exemplo: registre `Meu gato se chama Alt.` e consulte `Qual nome do meu gato?`. O resultado apresenta o trecho observado e o endereço de origem. Se também registrar `Meu gato se chama Bia.`, ambos podem aparecer; o MVP não escolhe qual é verdadeiro. A consulta não registra automaticamente sua pergunta. Para ensiná-la como observação, use explicitamente o formulário de registro.

## Contratos do fluxo

| Operação | Comportamento |
| --- | --- |
| `POST /api/entries` | Texto bruto, nome de memória e origem `user_turn`/`assistant_generated`; gera endereço UUID e sequência, observa nativamente e confirma flush antes de retornar 201. |
| `GET /api/entries?scope=principal` | Histórico completo limitado a 4096 entradas por memória; inclui conteúdo gerado com sua origem identificada. |
| `POST /api/query` | Texto bruto e escopo explícito; recuperação estrutural nativa com até 16 contextos, mais conteúdo exato observado. Não altera observações, sequências ou vínculos. |
| Hipóteses opcionais | `experimental:true` integra `copy_relations` sobre o histórico persistido; limite de 64 entradas/4096 caracteres de histórico. Exceder o limite retorna 413, sem analisar um recorte parcial. |
| Sem conteúdo | `UNRESOLVED`, lista vazia e nenhuma resposta inventada. |
| Conteúdo recuperado | `CANDIDATES`, textos observados com todas as origens aceitas daquele texto. Não equivale a resposta factual ou resolução de conflito. |
| Envelope | Sempre `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`, `query_recorded:false`, qualidade factual `NOT_EVALUATED`. |

As rotas de dados exigem `X-Memoria-Key`. A página inicial contém apenas a interface. Os nomes de memória admitem letras ASCII, números, traço e sublinhado, até 64 caracteres; o escopo aceito é transportado como `conversation:mvp:<nome>`, sem deduzir intenção da pergunta. Textos preservam inclusive espaços e Unicode, mas texto vazio ou só espaços é rejeitado.

Conteúdo gerado é armazenado no campo nativo separado `conversation:mvp:<nome>:generated`. Portanto não treina o campo de recuperação do usuário. Ele permanece no histórico; na projeção experimental vira apenas barreira da sequência local, excluída de raízes/fontes pelo adaptador já existente. Seus endereços reais de armazenamento continuam no histórico, enquanto origens de relações inferidas apontam exclusivamente para usuários. Cópias de um texto mantêm endereços distintos e não são votos de verdade.

O lançador mantém um mutex durante operações completas e usa `flock` para impedir outro processo deste MVP no mesmo diretório. O token do MVP é um hash dos dois tokens regionais nativos; antes e depois da consulta, o histórico completo precisa ser igual. Uma mudança detectada retorna 409 sem resultados parciais. Isso não é garantia de snapshot global contra um escritor externo que ignore o protocolo. O diretório pertence exclusivamente a este protótipo, com uma instância/worker; não o compartilhe com outro lançador de produto.

## Verificação e falhas preservadas

O relatório `benchmark-results/trajectory-local-mvp-http.json` vem de processos reais do servidor, requisições HTTP em loopback, término/reabertura do processo e restauração em outro diretório de uma cópia feita com o processo fechado. São **12/12 controles de integridade**: interface HTTP, autenticação, consulta sem alteração, ausência de qualificação, exclusão de fontes geradas, escopo, duplicatas endereçadas, nomes concorrentes, igualdade completa da consulta e do histórico após reinício/restauração.

Nos sete exemplos públicos sintéticos, a recuperação tem **5/7 conjuntos exatos**. Os exemplos de reunião e viagem recuperam o respectivo trecho. As consultas vazia, sem sobreposição e em memória contendo somente texto gerado abstêm-se. As duas falhas permanecem:

- Perguntar o nome do gato recupera os dois nomes esperados, mas também o trecho sobre onde ele dorme.
- Perguntar a cor do gato, que nunca foi informada, recupera os mesmos três trechos. A API continua sem resposta factual, mas a recuperação não reconhece sozinha a ausência desse atributo.

O relatório conserva `FAIL_EXTRA_OR_MISSING_CONTENT`; não ajustamos vocabulário ou o motor para decorar esses exemplos. Esta amostra não mede compreensão geral da linguagem. O gate falha seu processo por quebra de integridade, e relata separadamente falhas semânticas; CI verde não significa precisão semântica aprovada.

Testes locais: **19 passed** incluindo 11 contratos novos do MVP, adaptador estrutural nativo, API estrutural existente e UI de produto existente. Cobrem ainda propostas/abstenções de quatro fixtures estruturais, barreiras geradas, múltiplos alvos, limite experimental, validação, concorrência e rejeição de escrita entre chamadas. Esses fixtures não são um teste de compreensão de perguntas reais.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so \
MEMORIA_NATIVE_LIB=build/trajectory-native/libmemoria_mobile.so \
PYTHONPATH=src python -m pytest -q \
  tests/test_trajectory_local_mvp.py tests/test_native_structural_text_adapter.py \
  tests/test_product_structural_observation.py tests/test_product_webui.py

PYTHONPATH=src python scripts/trajectory_local_mvp_gate.py \
  --library build/trajectory-native/libmemoria_mobile.so
```

Backup: feche o processo e copie integralmente `data/local-mvp`. Para restaurar, use a cópia como `--data-dir`, com a mesma biblioteca. O gate verifica esta modalidade. Backup online, migração entre versões, queda abrupta de energia e serviço remoto não foram validados neste incremento.

A tela é entregue com layout responsivo e apresenta resultados via `textContent`. Um teste de interação em JSDOM contra o servidor HTTP real passou: salvar, consultar, mostrar origem, manter HTML de uma entrada como texto, limpar resultados ao mudar memória, apresentar estado vazio e recuperar os botões após erro de validação, sem erros de script. JSDOM não valida renderização visual. A validação visual em navegador permanece pendente: o ambiente não tinha Chromium e o download do executável retornou um arquivo inválido. Não houve alegação de aprovação visual nem publicação remota. A CI inclui os testes do MVP e o gate HTTP junto à biblioteca nativa fixada; o novo commit ainda precisa executar esses checks.

## Próximo passo de produto

Experimentar esta tela com memórias e perguntas variadas do usuário, guardar os casos sem evidência, com conteúdo extra e com informações concorrentes, e melhorar a recuperação sem transformar a consulta em aprendizado implícito. Depois disso, integrar o fluxo ao servidor de produto existente e validar a distribuição desejada. Conversação autônoma, geração de linguagem sem LLM e qualificação factual continuam sem comprovação.
