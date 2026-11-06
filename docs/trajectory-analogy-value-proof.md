# Valores parcialmente repetidos e destinos com cauda constante

A política anterior exige três valores livres distintos nas três demonstrações. Esta extensão experimental conserva três variáveis de origem distintas, mas acrescenta duas possibilidades: um campo livre com dois valores distintos entre os três exemplos, ou uma cauda de destino inteiramente idêntica. Não muda o motor nem os seletores anteriores; une as rotas novas às antigas e conserva candidatos concorrentes.

No primeiro caso, prefixo, ponte, sufixo e alinhamento das cópias continuam exigidos. O veto por âncoras internas permanece ativo, incluindo o novo controle em que apenas dois corpos distintos contêm relações misturadas. No segundo caso, a cauda inteira é fixa: o candidato deve reproduzi-la exatamente. Uma cauda constante não é reinterpretada como valor livre e não autoriza um valor diferente.

## Bateria original, contratos preservados

| Política | Acertos / casos | Respostas corretas / positivas | Seleções indevidas | Ausências vazias / negativas |
| --- | --- | --- | --- | --- |
| Cópias repetidas | 142/168 | 18/44 | 0 | 124/124 |
| Valores parcialmente repetidos | 146/168 | 22/44 | 0 | 124/124 |

As sementes 20261026 e 20261027 dão os mesmos resultados. O ganho corresponde aos quatro positivos correlacionados de `two_equal_values`: consulta exata e contexto adicional, com e sem renomeação bijetiva. As outras onze famílias conservam exatamente os candidatos e as hipóteses anteriores. Os relatórios ficam em `benchmark-results/trajectory-analogy-value-{development,reserved}.json` e incluem as decisões da política anterior.

A qualidade continua **FAIL**, com 22 respostas positivas sem recuperação por lote. Na família `constant_value`, o quarto destino usa um valor diferente dos três exemplos de treinamento. A extensão registra o padrão constante, mas não seleciona esse destino; os quatro positivos dessa família continuam falhando. Não mudamos seu contrato para melhorar a contagem.

## Controles de cauda constante, com denominador próprio

Os relatórios incluem seis casos adicionais, três situações com e sem renomeação: uma raiz com a mesma cauda é recuperada; uma raiz com cauda diferente permanece sem candidato; duas caudas sustentadas por demonstrações preservam as duas raízes e deixam a hipótese vazia. Todos passaram nas duas sementes. Esses seis casos não entram no denominador de 168, para conservar a comparação histórica.

Sete testes novos verificam a repetição parcial, a falha positiva constante mantida no relatório, os controles de cauda fixa, ausência de ganho por payloads repetidos com apenas duas variáveis de origem, cauda fixa com cópias repetidas, recusa de corrupção, duas pistas, veto interno para dois corpos distintos e paridade/renomeação. Os 41 testes locais de analogia passaram. Cada leitura verifica restauração, aprendizagem e geração padrão inalteradas.

## Interpretação e limites

O ganho mostra que três identificadores distintos podem sustentar a forma do padrão mesmo quando dois resultados compartilham o valor. Não demonstra que qualquer campo de dois valores possa ser tratado como livre: essa é uma hipótese estrutural experimental, sujeita a contraexemplos. O ramo constante só confirma compatibilidade com uma cauda observada inteira; não estabelece verdade semântica nem descobre sozinho a divisão entre relação e valor.

As sementes e renomeações alteram endereços, não representam novas formas independentes. Não há política de pesos por frequência temporal. Repetir payloads não fornece as três variáveis exigidas, embora possa aumentar combinações de testemunhas. A enumeração continua sem garantia de eficiência para grandes memórias. Coincidências internas, inversão de cópia, bordas compartilhadas de valores e contexto sem prefixo continuam limitando a cobertura.

O modo `--strict-quality` retorna 1 enquanto a bateria principal for FAIL. A CI normal verifica integridade e executa os controles, sem declarar os gates de qualidade resolvidos. Runtime nativo e OFF.IA permanecem inalterados; os três gates pessoais nativos seguem pendentes.

Próximo passo: ampliar os contraexemplos de dois valores e verificar se a hipótese de campo livre produz escolhas indevidas quando relações diferentes não têm um delimitador interno comum. Isso precisa preceder a integração de qualquer relaxamento.
