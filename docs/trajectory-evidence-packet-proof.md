# Candidatos, sequência observada e autorização

Continuação do estudo de contexto fixo copiado. O novo diagnóstico monta um pacote somente leitura sobre o leitor anterior, conservando integralmente candidatos, quadros e hipótese anterior. Não modifica aprendizado, pesos, geração padrão, seletores anteriores ou runtime nativo.

Cada raiz registra separadamente correspondência de quadro e continuação exata observada. A segunda exige que a origem seja exatamente a consulta e que o destino seja a observação imediatamente seguinte na mesma hierarquia e stream. Não combina capturas, não salta uma entrada intermediária e não atribui intenção de resposta à adjacência. As testemunhas incluem endereços de ambas as ocorrências e de seus payloads. O contrato usa a ordem de ingestão do snapshot, não timestamps externos; importadores continuam responsáveis por preservar a sequência e barreiras de origem.

O pacote expõe `prior_structural_hypothesis` como diagnóstico, mas mantém `answer:null`, `qualified:false` e `UNQUALIFIED_STRUCTURAL_EVIDENCE` em todos os estados. Uma hipótese herdada pode continuar sendo indevida nos contraexemplos anteriores; envolvê-la no pacote não corrige sua seleção nem autoriza promovê-la a fato. Conflito considera todas as raízes recuperadas, sem dar prioridade à continuação exata.

## Intervenção sequencial

| Estágio | Raízes de continuação exata | Ocorrências dessas continuações |
| --- | --- | --- |
| Candidato por quadro | 0 | 0 |
| Três repetições de demonstração anterior | 0 | 0 |
| Consulta isolada | 0 | 0 |
| Consulta seguida da raiz candidata | 1 | 1 |
| Repetição desse par | 1 | 2 |
| Consulta seguida de outra raiz conhecida | 2 | 3 |

A consulta isolada acrescenta sua raiz; todas as etapas posteriores reutilizam payloads existentes. A nova sequência acrescenta informação de ocorrência endereçável sem novo conteúdo. A repetição do par aumenta o número de testemunhas, mas não o número de raízes nem um voto de certeza. A entrada concorrente conserva as duas raízes e informa conflito.

Seeds 20261107/20261108 e renomeação bijetiva preservam o desenho: são controles correlacionados, não baterias independentes de generalização. Seis testes verificam intervenção, conservação de candidatos, ausência de saltos/junções entre capturas, separação de hierarquias, consulta exata, equivalência dos contratos latentes e renomeação. Toda leitura verifica restauração, estado de aprendizado e geração padrão inalterados; testemunhas são resolvidas aos endereços observados.

## Limite medido

Os contratos `whole_tail` e `latent_relation` ainda recebem exatamente os mesmos dados, inclusive após acrescentar o par exato consulta/destino. Seus pacotes continuam idênticos. A nova sequência comprova que a continuação aconteceu, mas não revela os papéis ocultos definidos pelo avaliador. O relatório marca `integrity_status:PASS` e `semantic_quality_status:UNRESOLVED`; não calcula uma taxa de acerto factual nem reclassifica as falhas anteriores como sucesso.

Relatórios completos: `benchmark-results/trajectory-evidence-packet-{development,reserved}.json`. Reprodução: `python scripts/trajectory_evidence_packet_probe.py --seed 20261107` e `--seed 20261108`. As baterias anteriores 40/48, 66/72 e contraexemplos sem marcação permanecem com seus próprios denominadores e falhas. OFF.IA e os três gates pessoais nativos permanecem inalterados.

Próxima investigação: observações que mostrem separadamente variação de relação e de valor, mantendo candidatos e conflitos explícitos. Apenas duplicar uma sequência ou trocar seu rótulo no avaliador não fornece essa discriminação.
