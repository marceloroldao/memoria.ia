# Região observada, rotas estruturais e papéis ocultos

Continuação de `6bf511c`. O incremento mantém motor, leitores anteriores, runtime nativo e OFF.IA inalterados. Adiciona uma projeção experimental de leitura por região de proveniência e compara sucesso estrutural com um controle de intenção ausente nas observações.

## Como a região entra

O chamador fornece um `hierarchy_id` que já acompanha as ocorrências observadas. O diagnóstico reconstrói uma **memória temporária** somente com essas ocorrências, preservando payloads, endereços, IDs, ordem, streams e configuração. Essa projeção evita reaproveitar índices derivados de regiões omitidas. Nenhuma consulta, saída gerada ou rótulo de resposta entra nesse replay; a memória original não é modificada.

Sem região, a leitura continua global. Região desconhecida produz uma projeção vazia; ID vazio ou inválido é rejeitado. A região é um escopo escolhido explicitamente, não uma situação descoberta autonomamente a partir do conteúdo. Seus IDs são opacos e também passam por renomeação no controle.

O leitor e o ledger anteriores são executados sobre essa projeção. Candidatos da leitura global são conservados na leitura global; ausência em uma região não declara que a evidência de outra região seja falsa. Todas as molduras do resultado regional têm testemunhas nas ocorrências selecionadas. O replay temporário não promete manter a mesma decomposição interna dos índices da memória inteira: preserva conteúdo/endereço e verifica paridade da própria projeção após restauração.

## Intervenções

Duas regiões recebem os mesmos três pares de demonstração, mas raízes reservadas diferentes. As duas raízes copiam exatamente o mesmo corpo e diferem no valor final. No controle, as cópias são adjacentes no destino; a equivalência dos cortes permanece. Uma terceira região recebe apenas uma raiz isolada, sem os pares necessários para aprender a moldura. A consulta reservada não é ingerida.

| Leitura | Estado inicial | Repetição em outra região | Rival posterior na mesma região |
| --- | --- | --- | --- |
| global | duas raízes concorrentes | duas raízes concorrentes | duas raízes concorrentes |
| primeira região | primeira raiz | primeira raiz | ambas as raízes; hipótese única suspensa |
| segunda região | segunda raiz | segunda raiz | segunda raiz |
| raiz isolada sem molduras | vazia | vazia | vazia |
| região desconhecida | vazia | vazia | vazia |
| corpo desconhecido | vazia | vazia | vazia |

A rival já existia globalmente. Sua chegada à primeira região cria uma nova ocorrência local, sem novo payload global. Repetir observações na segunda região não altera o resultado completo da primeira projeção. Um controle adicional divide três demonstrações entre regiões incompletas: a leitura global aprende uma moldura, enquanto cada projeção permanece sem essa moldura. Não se emprestam testemunhas fora do escopo.

## O que foi e o que não foi demonstrado

Seeds 20261127/20261128, cada um também sob bijeção de símbolos e IDs de região:

- **roteamento estrutural: 36/36 PASS**;
- 10/10 hipóteses estruturais únicas, 8/8 conflitos, 18/18 ausências vazias;
- 18/18 casos com todos os alvos retidos e zero falsas hipóteses únicas nesta bateria.

Esses são fixtures opacos e correlacionados com região explícita, molduras aprendidas e cópias exatas. O resultado não substitui os FAILs anteriores 28/32, 148/160, 124/168, 98/126 ou os gates pessoais nativos. Também não resolve a fronteira interna das cópias adjacentes.

## Gêmeos com papéis ocultos

Dois motores independentes restauram as mesmas observações e recebem a mesma consulta e a mesma região. Seus snapshots e resultados completos têm hashes iguais. Só depois dessas leituras, o avaliador atribui contratos distintos: raiz como resposta pretendida versus evento adjacente sem intenção de resposta. Esses papéis não entram na ingestão, nos IDs da região ou na API de leitura.

O leitor conserva `answer:null`, `qualified:false`: **2/4 avaliações de resposta passam**, com duas respostas positivas ausentes e zero respostas falsas. Um comparador inseguro, usado apenas no avaliador, promove a hipótese estrutural a resposta: também passa 2/4, mas produz **duas respostas falsas**. Esse comparador não é instalado no diagnóstico.

Portanto o sucesso estrutural é PASS, mas o campo `semantic_quality_status` permanece **FAIL** para esses contratos de resposta. Região ajuda a localizar a evidência quando seu escopo já é conhecido; não revela um papel que não foi observado. Esse contraexemplo não prova que novas observações jamais possam distinguir os papéis.

## Validação e CI

Oito testes novos cobrem separação regional/global, origem das testemunhas, repetição estrangeira, rival local, escopos desconhecidos/incompletos, renomeação, gêmeos e denominadores separados. Cada leitura verifica restauração e memória/aprendizado/geração originais inalterados. Os dois seeds reproduziram os totais, e o modo estrito retornou 1 devido ao FAIL de resposta. Regressões locais dos probes e consumidores estruturais: **239 passed, 1 optional BDR skip**. O resumo de desenvolvimento, suas raízes/endereços, fingerprints dos gêmeos e o hash do relatório completo foram reproduzidos exatamente. Compilação Python e `git diff --check` passaram.

A execução anterior `37380015148` foi cancelada aproximadamente dez minutos após o início do job `proof`, durante comprimentos cruzados; os passos do diagnóstico anterior e regressões finais foram pulados. O job tinha `timeout-minutes: 10`; os logs registram cancelamento, sem falha de asserção nesse ponto. `native-bridge` e seis outros workflows aplicáveis passaram. Este incremento amplia apenas o limite do job `proof` para vinte minutos, preservando todas as verificações. A nova CI ainda precisa concluir.

```
python -m unittest discover -s tests -p test_trajectory_region_evidence_probe.py
python scripts/trajectory_region_evidence_probe.py --seed 20261127 --summary
python scripts/trajectory_region_evidence_probe.py --seed 20261128 --summary
python scripts/trajectory_region_evidence_probe.py --seed 20261128 --summary --strict-quality
```

Resumos com IDs, raízes, hashes dos resultados regionais e dos relatórios completos: `benchmark-results/trajectory-region-evidence-{development,reserved}.json`. Sem `--summary`, o script reproduz pacotes, comparação por raiz/corte, testemunhas e proveniência completos.

## Próxima investigação

Comparar evidência estrutural regional com vínculos de resposta explicitamente observados, reutilizando o contrato nativo `reply_to` já existente. O vínculo deve distinguir episódios sem converter a resposta em fato. Preservar conflitos locais, referências de origem e os gêmeos que continuam sem vínculo observado; não inferir um vínculo apenas da proximidade. Antes de integrar esse caminho, manter visíveis as falhas do gate pessoal nativo e verificar o comportamento após reabertura.
