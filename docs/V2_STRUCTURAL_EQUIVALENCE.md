# V2 — Equivalência estrutural emergente entre trajetórias

Status: experimento, não qualificado para merge.
Issue: #298.

## Motivação

A V2 preserva a experiência e resolve consultas estruturalmente próximas, mas ainda não generaliza certas reformulações que a baseline restart3 resolve por sua camada semântico-relacional. O caso de referência é:

- experiência: `eu tenho um gato que se chama Lotus`
- experiência: `ele tem um irmão, que se chama Vibe`
- consulta: `qual nome dos meus gatos?`

A baseline restart3 qualificada encontra Lotus; a V2 atual não encontra terminal para a reformulação, embora os controles estruturais encontrem Lotus e Vibe corretamente.

O objetivo não é adicionar conhecimento linguístico ao motor. O experimento testa se equivalência pode emergir da geometria recorrente das experiências.

## Princípio

Uma configuração A e uma configuração B não se tornam equivalentes porque compartilham palavras, porque uma regra externa assim determina ou porque um modelo semântico as aproxima. Elas só podem adquirir uma ligação derivada quando ocorrências independentes mostram convergência repetida para a mesma região terminal/futuro.

A ligação é uma hipótese estrutural revogável, nunca uma identidade ontológica rígida.

## Objetos mínimos

### StructuralSignature

Representação determinística e ordenada da configuração observada, derivada apenas dos endereços/nódulos já materializados na trajetória.

Campos mínimos:

- `signature_id`: hash determinístico do conjunto/ordem relevante;
- `members`: endereços atômicos ou compostos;
- `trajectory_id` / `occurrence_id` de origem;
- `lineage_id` para controle de independência.

### ConvergenceEvent

Evidência de que uma assinatura observada alcançou uma determinada região terminal.

Campos mínimos:

- `signature_id`;
- `terminal_region_id`;
- `occurrence_id`;
- `lineage_id`;
- `sequence`;
- `path_digest` opcional para auditoria.

### StructuralEquivalenceCandidate

Hipótese derivada de que duas assinaturas podem ser usadas como rotas alternativas para a mesma região.

Campos mínimos:

- par canônico de `signature_id`;
- conjunto de regiões terminais compartilhadas;
- contagem de convergências independentes;
- contagem de divergências independentes;
- estado: `insufficient`, `candidate`, `supported`, `contradicted`;
- proveniência completa dos eventos usados.

## Independência

Repetição não é evidência independente quando vem da mesma linhagem. Duplicações, replay, saída de LLM derivada da própria memória ou cópias da mesma ocorrência não podem elevar suporte.

O primeiro protótipo deve usar cardinalidade de `lineage_id` independentes, não frequência bruta.

## Ativação conservadora

A equivalência não pode vencer evidência atômica direta mais forte. Ordem de precedência experimental:

1. correspondência atômica/composta direta;
2. trajetória explícita observada;
3. equivalência estrutural suportada;
4. unresolved.

Se duas equivalências suportadas apontarem para regiões incompatíveis e não houver evidência direta que desempate, a resolução deve permanecer ambígua/fail-closed.

## Revogação

Uma equivalência é dinâmica. Nova experiência pode:

- reforçar convergência;
- revelar que a convergência era contextual;
- dividir uma assinatura em regimes diferentes;
- contradizer a hipótese.

Portanto, nenhuma equivalência deve ser gravada como verdade irreversível.

## Consulta read-only

Resolver uma consulta não cria, reforça nem modifica equivalência. Apenas ingestão/observação de nova experiência pode produzir `ConvergenceEvent`.

## Hipótese de generalização

Uma reformulação nova pode inicialmente não possuir rota. Se sua configuração já tiver sido observada em outros episódios convergindo para regiões que também são alcançadas por configurações conhecidas da memória atual, o resolver pode atravessar a equivalência estrutural e alcançar candidatos terminais.

Esse mecanismo não garante que o primeiro fixture Lotus/Vibe seja resolvido com apenas duas frases. Isso é intencional: sem evidência recorrente suficiente, o sistema deve preferir `unresolved` a inventar equivalência.

## Bateria adversarial obrigatória

1. Convergência verdadeira repetida por linhagens independentes.
2. Cem repetições da mesma linhagem: não podem equivaler.
3. Convergência acidental única: não pode equivaler.
4. Duas assinaturas convergem inicialmente e depois divergem: candidato deve ser rebaixado/revogado.
5. Hub terminal compartilhado por centenas de trajetórias não relacionadas: não pode fabricar consenso.
6. Duas equivalências conflitantes: fail-closed.
7. Restart: mesmas assinaturas, eventos, estado e ordenação.
8. Query read-only: snapshot antes/depois idêntico.
9. Fixture restart3 Lotus/Vibe preservado como hard generalization probe, sem regras lexicais específicas.

## Critério para considerar esta linha promissora

- zero falso consenso na bateria adversarial;
- determinismo antes/depois de restart;
- nenhuma mutação em consulta;
- nenhuma lista de sinônimos, regex semântica, embedding, rede neural ou peso aprendido;
- melhoria mensurável em reformulações apenas quando existe histórico estrutural suficiente;
- custo de consulta e crescimento de estado medidos em 100 / 1.000 / 10.000 trajetórias.

## Não objetivo

Este experimento não substitui ainda a camada semântico-relacional do restart3, não altera a ABI mobile, não muda RC7 e não autoriza merge da V2 em `main`.
