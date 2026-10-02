# Fronteiras candidatas sem separador comum

A extensão somente leitura aprende correspondências posicionais entre duas partes contíguas da origem e suas cópias exatas no destino. Não exige um símbolo separador comum entre as partes. Usa três pares adjacentes observados, com prefixo/sufixo comuns da origem, três valores distintos em cada parte e três caudas variáveis distintas. Ordem das cópias, cabeçalho, ponte entre cópias, ponte após a segunda cópia e sufixo do destino são derivados das demonstrações; ordem invertida também é representável.

Para cada demonstração, conserva os endereços das raízes, o corte absoluto na origem, as duas partes copiadas e suas posições no destino. Cópias sobrepostas ou múltiplas são rejeitadas. Uma âncora comum interna nas caudas veta o quadro, sem apagar sua evidência. Não usa rótulos semânticos, pesos de repetição ou geração de novas raízes.

Na consulta, enumera **todos** os cortes não vazios da região variável de cada quadro, sem fixar o comprimento visto no treino. Registra cortes com raízes observadas e cortes sem suporte. Conserva as rotas anteriores e todas as novas raízes concorrentes. Uma raiz sustentada só pela extensão continua candidata; não recebe uma hipótese única. Uma hipótese herdada só permanece quando não há raiz rival nem suporte parcial nas novas fronteiras. O pacote conserva a hipótese herdada separadamente, inclusive quando ela é indevida nos contraexemplos anteriores; continua `answer:null`, `qualified:false`.

## Comparação no mesmo contrato da ablação

O diagnóstico de separadores agora aceita um leitor opcional; o leitor padrão e seus resultados anteriores permanecem iguais. Nenhuma fixture ou expectativa foi mudada. Os três layouts continuam com todos os destinos byte a byte iguais; a extensão é avaliada com duas sementes opacas novas, 20261113/20261114, mantendo o mesmo desenho e versões por bijeção.

| Layout | Casos corretos anteriores | Extensão | Todos os alvos recuperados antes | Extensão |
| --- | --- | --- | --- | --- |
| Explícito | 42/42 | 42/42 | 18/18 | 18/18 |
| Ausente | 24/42 | 28/42 | 0/18 | 18/18 |
| Ambíguo | 28/42 | 28/42 | 18/18 | 18/18 |

No layout sem separador, os destinos reservados agora aparecem com testemunhas posicionais. As quatro consultas de conflito passam a conservar as duas raízes esperadas e suspendem a hipótese. Os 14 positivos que exigem resposta continuam falhando: há uma divisão sustentada e outras divisões válidas sem raiz observada. A extensão não descarta essas divisões para autorizar a primeira.

Total: **98/126 FAIL**, ante 94/126 na política anterior; 14/42 hipóteses estruturais esperadas, 12/12 conflitos preservados, 72/72 ausências vazias, 54/54 casos com todos os alvos recuperados e zero seleções únicas indevidas **nesta bateria**. O ganho de quatro casos mede conservação de conflitos, não novas respostas. O modo estrito retorna 1. O resultado não altera os denominadores ou falhas dos experimentos mais antigos.

São controles correlacionados: sementes renomeiam endereços; repetição e contexto inicial reutilizam a mesma forma. Não são 18 demonstrações independentes de compreensão nem uma taxa de acerto factual. O protocolo exige exatamente duas partes copiadas, duas bordas externas comuns e três exemplos distintos; ainda não aprende segmentação arbitrária ou campos sem cópia exata.

## Verificação e limites

Sete testes verificam métricas e respostas ainda suspensas, todos os cortes sem suporte visíveis, paridade nos layouts anteriores, repetição/conflitos/proveniência por estágio, bijeção e raízes endereçadas, cópia em ordem inversa/cópia extra/âncora interna e ausência de pares entre capturas distintas. Um contraexemplo anterior de campo latente continua produzindo a hipótese herdada indevida, explicitamente conservada como diagnóstico não qualificado; esta extensão não é uma solução geral para os campos semanticamente indistinguíveis.

Toda leitura verifica restauração, aprendizado e geração padrão inalterados. Cada testemunha de quadro é conferida contra o corte exato da origem e as posições copiadas no destino. Repetir pares não muda os destinos recuperados nem elimina as alternativas; a raiz rival só aparece na proveniência depois da observação correspondente.

Relatórios completos: `benchmark-results/trajectory-boundary-candidates-{development,reserved}.json`. Reprodução: `python scripts/trajectory_boundary_candidates_probe.py --seed 20261113` ou `--seed 20261114`. A CI verifica integridade e mantém o FAIL de qualidade. Runtime nativo, OFF.IA e os três gates pessoais continuam inalterados. A enumeração de trios, produtos de cortes e raízes não tem garantia de eficiência; não foi otimizada para produção.

Validação local: sete novos testes e 157 testes anteriores passaram, com um teste opcional de BDR pulado. Ambos os lotes reproduziram os mesmos agregados e o modo estrito foi confirmado retornando 1 para as respostas ainda suspensas. O controle de âncora interna usa o marcador entre duas partes variáveis da cauda; um marcador na borda fixa pertence à ponte e não é uma âncora interna.

Próxima investigação: intervenções que tragam raízes para outras divisões candidatas e distingam suporte parcial, convergência para a mesma raiz e conflito entre raízes. Apenas repetir o mesmo quadro ou assumir comprimentos fixos não estabelece essa discriminação.
