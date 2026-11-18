# Contexto fixo copiado e preservação de relações específicas

Esta extensão experimental do leitor conserva quadros de um campo variável com ponte vazia após a cópia, desde que haja contexto fixo da origem também copiado no cabeçalho do destino. Não modifica os leitores anteriores, a geração padrão ou o motor. O diagnóstico de pistas repetidas agora aceita um leitor como argumento opcional; seu leitor padrão e seus relatórios anteriores permanecem iguais.

O aprendizado usa trios de pares observados em sequência, com três trechos variáveis distintos, delimitadores de origem não vazios, uma cópia exata do trecho variável em cada destino, cabeçalho de destino constante e três valores finais distintos. A ponte após a cópia deve ser vazia; quadros com ponte existente continuam nas rotas anteriores. Todos os trechos máximos comuns entre cada limite fixo da origem e o cabeçalho do destino são registrados com posições. Uma âncora interna comum nos valores veta o quadro, sem apagar suas testemunhas.

A leitura une as raízes novas e anteriores, conserva testemunhas e rejeita destinos que repetem o trecho variável. Não atribui prioridade ao quadro específico ou ao amplo. Uma raiz sustentada somente pela nova rota fica como candidata, com hipótese suspensa (`COPIED_CONTEXT_CANDIDATE_ONLY`). Uma hipótese única já autorizada pelo leitor anterior só permanece se não houver raiz rival nem suporte parcial anterior. Se a leitura anterior suspendeu a resposta por uma divisão sem suporte, a extensão mantém essa suspensão.

## Comparação no mesmo contrato

| Medida por lote | Leitor anterior | Extensão |
| --- | --- | --- |
| Casos corretos | 32/48 | 40/48 |
| Respostas corretas | 8/16 | 8/16 |
| Conflitos preservados | 8/16 | 16/16 |
| Ausências vazias | 16/16 | 16/16 |
| Seleções únicas indevidas | 8 | 0 |

Os exemplos e expectativas são os mesmos da bateria de pistas repetidas. A relação específica com a primeira pista fixa agora é aprendida e sua raiz conservada; depois da forma ampla, ambas as raízes ficam candidatas e a hipótese é suspensa. Os oito positivos antes não recuperados continuam falhas de resposta, pois conservar um candidato não equivale a autorizar uma hipótese. Repetir um par não cria novas raízes nem resolve esse conflito. Sementes 20261105 e 20261106 mudam somente símbolos opacos; contextos iniciais e renomeações são controles correlacionados. O resultado anterior 32/48 permanece registrado, assim como o 66/72 de divisões ambíguas.

## Contraexemplo adicional: contexto copiado não define papéis

Quatro controles são repetidos por bijeção, com denominador separado. A ablação que autoriza a nova raiz única alcança **48/48** na bateria principal, mas **6/8 FAIL** nos controles, incluindo **duas seleções únicas indevidas**. Essa autorização foi rejeitada e aparece separadamente no relatório (`REJECTED_UNIQUE_AUTHORIZATION`); não é o comportamento padrão. Ausência de contexto fixo copiado impede a nova rota; uma âncora interna veta a rota. Os outros dois controles têm exatamente os mesmos pares, consulta, raiz isolada e resultado, mas contratos distintos:

- `whole_tail`: a cauda inteira é o valor livre; a seleção é esperada.
- `latent_relation`: a primeira parte da mesma cauda representa uma relação latente diferente; a ausência é esperada.

A ablação seleciona a mesma raiz em ambos. Os papéis dos campos não estão marcados nos dados, e o contexto fixo copiado não resolve essa indistinção. O padrão conservador mantém a raiz candidata, mas suspende a hipótese nos dois contratos: **4/8 FAIL**, sem seleção única indevida. O positivo segue sem resposta e o negativo que exige ausência vazia segue falhando, pois há um candidato; nenhum dos dois foi reclassificado. O relatório informa `main_quality_status=FAIL`, `control_quality_status=FAIL` e **`quality_status=FAIL`**. Não somamos os controles ao denominador de 48 nem declaramos a política apta para integração. Esta suspensão não corrige as seleções indevidas herdadas das rotas antigas, que continuam explicitamente testadas.

## Verificação e próximos limites

Relatórios: `benchmark-results/trajectory-analogy-fixed-context-{development,reserved}.json`. Registram quadros, trechos fixos copiados, posições, âncoras, pares testemunhas, leitura anterior, candidatos e proveniência por estágio. Leituras verificam restauração exata, geração e aprendizagem inalteradas e endereçamento das testemunhas.

Sete testes cobrem conservação de candidatos e conflitos, indistinção dos contratos latentes e recusa da autorização nova, contexto obrigatório e veto interno, cópia adicional no destino, igualdade de candidatos e hipóteses nos 12 cenários da bateria opaca anterior, suspensão por suporte parcial e renomeação/falha anterior sem marcação. Os contraexemplos anteriores continuam falhando; igualdade de regressão não significa segurança semântica. O modo `--strict-quality` retorna 1 devido aos positivos sem resposta e controles novos. A CI verifica integridade e mantém os FAIL nos relatórios.

O runtime nativo, OFF.IA e os três gates pessoais não foram alterados. A enumeração de trios e substrings continua sem garantia de eficiência. Próxima direção: distinguir explicitamente candidato recuperado de hipótese autorizada em rotas com campos não identificáveis, preservando possibilidades e registrando que novas observações precisam trazer informação discriminante, não apenas repetir os mesmos dados.
