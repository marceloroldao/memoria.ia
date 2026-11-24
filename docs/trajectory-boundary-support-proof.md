# Suporte observado entre divisões concorrentes

Este diagnóstico somente leitura resume os cortes do pacote anterior, sem modificar o leitor, o seletor ou a memória. Por quadro, mantém duas medidas separadas: cobertura (`EMPTY`, `PARTIAL`, `COMPLETE`) e relação entre raízes (`EMPTY`, `SINGLE_ROOT`, `MULTIPLE_ROOTS`). A interseção inclui também os conjuntos vazios: uma divisão sem raiz impede concordância completa. Unanimidade exige que **cada** corte tenha exatamente a mesma raiz única; uma raiz comum acompanhada de uma rival não satisfaz essa condição.

O resumo é por quadro, não uma autorização global entre todos os quadros, rotas herdadas ou interpretações semânticas possíveis. Conserva o pacote completo, todos os cortes vazios e sustentados, testemunhas posicionais e hipóteses herdadas. Não soma repetições, não elimina fronteiras e não produz raízes novas. Tanto o resumo quanto o pacote continuam `answer:null`, `qualified:false`.

## Intervenções sequenciais

Três pares demonstram duas partes copiadas em um destino com separador entre as cópias. A consulta reservada tem quatro símbolos variáveis e, portanto, três cortes possíveis. Novas raízes são explicitamente observadas em capturas isoladas, evitando criar pares de treinamento ao introduzir os destinos do teste.

| Estágio | Cortes sustentados | Raízes distintas | Diagnóstico |
| --- | --- | --- | --- |
| Sem destino reservado | 0/3 | 0 | Vazio |
| Primeira raiz | 1/3 | 1 | Parcial, raiz única |
| Duas repetições da primeira raiz | 1/3 | 1 | Mesmo suporte, mais ocorrências |
| Rival no mesmo corte | 1/3 | 2 | Parcial, conflito |
| Raiz para segundo corte | 2/3 | 3 | Parcial, conflito |
| Raiz para terceiro corte | 3/3 | 4 | Completo, conflito |

Outro controle omite o separador **no destino**: as cópias são contíguas e todos os cortes concatenam exatamente o mesmo corpo observado. Uma única raiz sustenta todos os cortes de cada quadro; duas repetições não alteram o diagnóstico. Uma rival de cauda, posteriormente observada, passa a sustentar todos os cortes junto com a primeira raiz e retira a unanimidade. Isso é equivalência de concatenação, não três evidências independentes de uma relação verdadeira nem descoberta da fronteira pretendida.

Cada layout também tem uma versão por bijeção de todos os símbolos. Cada lote (20261115 desenvolvimento, 20261116 reservado) tem **20/20 diagnósticos esperados**. São testes correlacionados de transições e invariância, não uma taxa de respostas corretas. A bateria estrutural anterior continua **98/126 FAIL**; seu denominador não foi misturado com estes 20 casos nem reclassificado. O relatório conserva esse resultado como referência marcada `recomputed:false`; os testes anteriores o recalculam separadamente.

## Verificação e limites

Seis novos testes verificam: separação das métricas; repetição sem votos e com três endereços de ocorrência; progressão de cobertura e retenção monotônica das raízes nestas intervenções; concordância desfeita por rival sem resposta autorizada; bijeção e reprodução do resumo; raiz comum com rival, corte vazio e ausência de quadros. Toda captura passa pela verificação anterior de leitura sem mutação, restauração fria e testemunhas posicionais.

Relatórios completos: `benchmark-results/trajectory-boundary-support-{development,reserved}.json`, incluindo proveniência por estágio e endereços de ocorrência dos candidatos. Reprodução: `python scripts/trajectory_boundary_support_probe.py --seed 20261115` ou `--seed 20261116`. O comando falha se as expectativas do diagnóstico não forem satisfeitas; o sucesso não representa aprovação semântica. A CI executa os testes e ambos os lotes, mantendo as falhas de qualidade dos experimentos anteriores.

Runtime, aprendizagem, geração padrão, seletores anteriores, OFF.IA e gates pessoais nativos permanecem inalterados. A enumeração mantém o custo e as hipóteses restritas do leitor anterior. Cobertura mede apenas cortes enumerados dentro dos quadros aceitos; não representa todas as interpretações possíveis. Próxima investigação: observações iguais com papéis latentes distintos, inclusive quando todos os cortes concordam, para delimitar o que este suporte consegue identificar sem informação adicional.

Validação local: **204 testes passaram, um teste opcional de BDR foi pulado**, incluindo seis testes novos, os probes anteriores e os consumidores estruturais existentes. Ambos os relatórios reproduziram 20/20 controles do diagnóstico. `git diff --check` passou.

O limite da concordância completa foi testado em [Concordância completa e papéis não observados](trajectory-boundary-roles-proof.md), incluindo sequências exatas iguais sob contratos diferentes e as falhas de resposta dos dois comparadores.
