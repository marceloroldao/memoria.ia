# Relações inferidas por testemunhos positivos de cópia

Continuação de `8cb021b`, cujos sete workflows aplicáveis passaram, incluindo trajetória `37659778915`. Este ensaio usa contextos brutos observáveis diferentes, copiados entre fontes e destinos de demonstrações sequenciais. Reutiliza o aprendizado de molduras/cortes existente para buscar ocorrências posteriores de raízes com testemunho positivo. Não instala seletor padrão, modifica o runtime ou atribui verdade a uma relação inferida. O PR #374 permanece em rascunho.

## Entrada e decisão

`copy_relations` conserva o diagnóstico contextual anterior completo, incluindo todas as rotas e rivais. O aprendizado recebe os cinco campos brutos já admitidos; vínculos `reply_to`, metadados de vizinhança nativa e papéis do avaliador continuam mascarados. As três demonstrações têm contextos e corpos diferentes, delimitadas por barreiras geradas excluídas da aprendizagem. Contexto/corpo novos da consulta não aparecem nas demonstrações. Os símbolos são opacos e renomeados injetivamente; nenhuma palavra ou marcador de pergunta identifica a resposta.

O leitor obtém `supported_roots` dos cortes já aprendidos, com cópias exatas e layout positivo. Enumera ocorrências posteriores no mesmo segmento local e conserva as que têm raiz sustentada. Cada relação mantém par alvo/origem e testemunhos de corte/layout/moldura; continua `INFERRED_SEQUENCE_RELATION / observed_reply_to:false`. A comparação `all_sequence_successors` conserva todos os usuários posteriores, sem filtro, para medir falsos vínculos da sequência.

O filtro usa a união dos testemunhos positivos; não exige que cortes desconhecidos deixem de existir. Conserva integralmente `unknown_cuts`, `cut_exclusion_used:false` e `global_reply_exclusion_guaranteed:false`. Falta de testemunho positivo não estabelece impossibilidade de outra resposta, nem permite excluir globalmente uma raiz ou intenção. As relações removidas continuam disponíveis nas rotas/pacote base. Uma raiz única inferida em um episódio permite apenas `proposal_payload_id`; o envelope conserva `answer:null`, `qualified:false`, `selected_target:null`, `selection_used:false`.

O runtime nativo admite vínculos explícitos no namespace `conversation:`. Os fixtures respeitam esse contrato; o namespace não informa ao aprendiz qual raiz ou relação é esperada. Os vínculos de referência são acrescentados somente depois da leitura, e sua intervenção deve preservar a saída completa. Reabertura fria e leitura sem alteração de linhas também são verificadas.

## Comparação no mesmo conjunto

São doze casos novos, diferentes dos dezesseis do ensaio anterior: contexto correspondente, contexto trocado, gêmeo sem relação, rival no mesmo contexto, conflito repetido, contexto desconhecido, contexto ausente, contexto escondido nas demonstrações, barreira gerada, raiz correspondente estrangeira, alvos múltiplos e separador explícito.

| Rota, nos 12 casos | Corretos | Falsos vínculos | Perdidos | Conjuntos exatos | Proposta/abstenção conforme referência |
| --- | ---: | ---: | ---: | ---: | ---: |
| vizinho imediato | 7 | 5 | 24 | 4/12 | 4/12 |
| vizinho com filtro estrutural | 7 | 5 | 24 | 4/12 | 4/12 |
| todos os sucessores sequenciais | 30 | 14 | 1 | 0/12 | 6/12 |
| candidatos estruturais posteriores | 30 | 5 | 1 | 6/12 | 6/12 |
| raiz contextual, com/sem escopo transportado | 0 | 1 | 31 | 3/12 | 6/12 |
| testemunho positivo de cópia | 28 | 1 | 3 | 8/12 | 8/12 |

Seeds 20261219/20261220 produzem as mesmas contagens e passam **86/86 controles de integridade cada**. São duas renomeações do mesmo desenho, sem generalização semântica comprovada. Há 31 vínculos de referência, dos quais 22 pertencem ao caso repetido. Sem esse caso, em onze situações a nova rota recupera 6, inventa 1 e perde 3; a rota estrutural ampla recupera 8, inventa 4 e perde 1. A melhora local de falsos vínculos cobra perda de duas relações que a rota estrutural recupera. Não comparamos diretamente essas contagens com as do conjunto anterior.

Nos controles de contexto correspondente/trocado, as demonstrações e duas raízes posteriores conservam-se. A consulta muda somente o contexto bruto visível; o corpo é o mesmo. A raiz proposta passa de `a` para `b`, com endereços verificados. Isso demonstra discriminação estrutural por contexto copiado observado, sem fornecer a identidade da resposta ao aprendizado. Não demonstra descoberta de intenção oculta.

No caso de rival do mesmo contexto, ambas as raízes mantêm testemunhos positivos e a proposta abstém-se por conflito. Com vinte cópias adicionais, permanecem 22 relações endereçadas e duas raízes; repetição não vence a rival. Dois alvos com a mesma raiz conservam seus episódios e abstêm-se de escolher o alvo pretendido.

## Limites e falhas preservadas

A nova rota perde três vínculos: demonstrações que não carregam o contexto na fonte; relação de referência atravessando uma barreira gerada; separador explícito não copiado para o destino. O último caso tem outra evidência estrutural no pacote base, mas o leitor de cortes de cópias contíguas não aprende um testemunho positivo correspondente. É uma limitação desta rota, não a ausência de todas as molduras possíveis do motor. A barreira não foi relaxada para melhorar o placar.

Contextos ausente/desconhecido conservam cortes desconhecidos e não recebem fallback global. Uma raiz com contexto correspondente em outra região não fornece origem local. Esses controles são referências de ausência construídas pelo avaliador; falta de vínculo em dados reais não prova que o conteúdo seja irrelevante.

O gêmeo sem relação tem exatamente as mesmas observações e saída completa do controle positivo. A proposta é correta em um e falsa no outro: **1/2 conjuntos de relações**, sem resolução da intenção escondida. Mesmo cópia e layout positivos não estabelecem que uma ocorrência seja resposta efetiva ou fato. Os relatórios conservam `FAIL_FALSE_OR_MISSING_RELATIONS`, `FAIL_HIDDEN_RELATION_TWINS` e qualidade factual `NOT_EVALUATED`. A melhora estrutural local não apaga esses FAILs.

## Verificação e continuidade

Regressão local com registro de saída: **314 passed, 1 optional BDR skip**, em 522,97 segundos. Os oito testes novos passaram, incluindo ambos os seeds nativos e as falhas de qualidade esperadas. Os dois resumos e hashes completos reproduziram byte a byte. Compilação Python e `git diff --check` passaram. A CI deste incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_copy_relation_probe.py
python scripts/trajectory_copy_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261219 --summary
python scripts/trajectory_copy_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261220 --summary
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. Resumos em `benchmark-results/trajectory-copy-relation-{development,reserved}.json`; sem `--summary`, conserva-se toda a evidência base/contextual. Permanecem os limites de snapshot do chamador, região explícita, intenção oculta e qualificação. Não houve geração de linguagem ou integração OFF.IA.

Próxima investigação: integrar testemunhos das molduras com separador à evidência positiva por ocorrência, medindo se recuperam o vínculo perdido sem reintroduzir raízes de outro contexto. A ausência de contexto observável e os gêmeos indistinguíveis devem permanecer como controles negativos.
