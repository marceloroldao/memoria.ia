# Exemplos adicionais e relações concorrentes

Este estudo mantém inalterados o motor, a analogia anterior e o veto experimental por âncoras internas. Adiciona observações em uma mesma memória e avalia a hipótese depois de cada intervenção. Os símbolos são opacos; a consulta mantém o mesmo formato. Não existem regras de vocabulário nem classificação semântica no seletor.

Inicialmente, três pares mostram três campos de relação diferentes. Duas raízes isoladas contêm o mesmo identificador consultado e duas outras relações. O veto preserva a evidência original e não autoriza nenhuma delas. Novos pares distintos passam a demonstrar a primeira relação de forma consistente. Depois, outra sequência demonstra a segunda relação.

| Etapa | Novas observações | Resultado exigido para consulta conhecida e novo prefixo |
| --- | --- | --- |
| Relações misturadas | Três pares e duas raízes isoladas | Ausência de candidatos elegíveis |
| Dois exemplos distintos | Dois pares com relação A constante | Ainda ausência |
| Conteúdo repetido | Três ocorrências adicionais do primeiro par de suporte | Ainda ausência; nenhuma raiz nova |
| Três exemplos distintos | Terceiro par de suporte para A | Raiz inteira observada da relação A |
| Ambas as relações sustentadas | Três pares distintos para B | Duas raízes inteiras; hipótese vazia |

O identificador consultado não aparece nos pares de treinamento. Consultas com identificador desconhecido ou duas pistas permanecem vazias em todas as etapas.

## Resultados

As sementes 20261020 e 20261021 produziram, cada uma, **40/40 PASS**, quatro respostas corretas, quatro conflitos preservados, 32 ausências vazias e zero seleções únicas indevidas. Cada lote contém cinco etapas, quatro consultas e duas versões por renomeação bijetiva. As sementes apenas mudam os endereços dos símbolos; não representam novas formas independentes. Os relatórios completos são `benchmark-results/trajectory-analogy-evidence-{development,reserved}.json`.

Cinco novos testes verificam a liberação da resposta, a ausência de ganho por repetição do payload, a preservação de ambos os destinos, os negativos e a renomeação. Toda leitura verifica paridade após restauração e ausência de mudanças no estado de aprendizagem ou na geração padrão. Candidatos e testemunhas elegíveis permanecem ligados aos endereços das observações. Para evitar repetição no JSON, os quadros e as âncoras bloqueadas ficam uma vez por etapa; as consultas conservam candidatos, hipóteses e testemunhas de ambas as políticas.

## O que este resultado permite concluir

Observações adicionais podem sustentar um quadro com uma relação constante, enquanto os quadros amplos anteriores continuam visíveis e bloqueados. Ao sustentar duas relações para a mesma pista, o experimento preserva ambas, sem transformar maior quantidade de rotas em votos de seleção.

Isso é acúmulo de evidência estrutural, não uma implementação de pesos adaptativos ou decisão por frequência temporal. O requisito de três variáveis distintas pertence ao diagnóstico anterior e continua sendo uma escolha conservadora, não uma lei da arquitetura. O conteúdo repetido reutiliza raízes e não libera respostas nesta bateria, mas pode gerar mais quadros com testemunhas em streams distintos; não afirmamos invariância do catálogo nem eficiência dessa enumeração.

O contrato de ausência com somente dois exemplos mede a política atual, não prova que dois exemplos nunca possam ser suficientes. A resposta única após três exemplos tampouco estabelece verdade semântica: demonstra compatibilidade com um quadro aprendido neste gerador controlado.

## Pendências mantidas

A bateria opaca anterior permanece em **132/168 FAIL**, com **8/44** respostas positivas, mesmo após o veto. O controle de coincidência interna continua mostrando perda de uma resposta legítima. A nova bateria fornece exemplos adicionais e tem denominador próprio; não substitui, corrige retroativamente ou amplia artificialmente o resultado anterior.

Nenhuma integração no motor, runtime nativo ou OFF.IA foi feita. Os três gates pessoais nativos continuam pendentes. Próximo passo: estudar variantes que não exijam prefixos e sufixos fixos, preservando as interpretações concorrentes e os controles de ausência; qualquer ganho deve ser comparado com a cobertura e os erros anteriores.
