# Auditoria técnica e sequência de evolução funcional — Memoria.ia

Data: 2026-09-09. Estado: auditoria inicial de código, testes, documentação e registros de integração; execução das etapas abaixo pendente.

## 1. Pedido do responsável pelo projeto

Registrar no repositório uma auditoria do projeto Memoria.ia e uma sequência de evolução que o leve a ser realmente funcional. Manter os achados, decisões, evidências, pendências e pontos de retomada no próprio repositório, para que o trabalho possa continuar mesmo após interrupções da aplicação ou limites de uso.

Este documento registra esse pedido e organiza sua execução. Não afirma que a auditoria interrompida anteriormente foi recuperada integralmente nem que as correções propostas aqui já foram implementadas.

Diretriz adicional registrada pelo responsável: o que é fato ou evidência não deve ser imposto rigidamente pela origem desde o início; possibilidades devem ser preservadas e sua sustentação deve evoluir por coincidência/convergência independente, reforço, contradição e trajetória temporal. A proveniência continua necessária. Repetições da mesma origem, cópias e ecos de uma LLM não equivalem a confirmações independentes.

## 2. Escopo e evidência desta revisão

Foram inspecionados a árvore de arquivos, README, roadmaps, auditoria Python/native, testes selecionados, código do pacote cognitivo mobile, workflows, registros de issues e resultados de Actions.

Referências examinadas:

| Linha | Referência | Interpretação |
| --- | --- | --- |
| main | `8dd86ef37e49dfe78668a0f301302c4ab9dae43d` | Base principal consultada antes desta documentação |
| Publicação RC7 | `ca4089cad0369da3a13c484c93cc4c97ee54cfaf` | Freeze funcional declarado no README; não confundir com HEAD atual |
| Integração mobile restart2 | `ef0161b8bf66f499d63bb28b816455c72e2ffdfd` | Freeze `mobile-relative-naming-recall-v1-integration-qualified`, registrado em #289 |
| Topologia temporal | `004478a18e91a91f010f9afdf720842b71dbc711` | Freeze histórico de #280; não substituir silenciosamente |

Limitações: não foi executada uma nova suíte local, compilação Android, teste em aparelho ou teste de invasão nesta revisão. Resultados de CI abaixo foram consultados; demais resultados históricos são atribuídos aos respectivos registros. Existência de teste não significa aprovação nesta sessão. O código completo de todos os módulos e o prompt efetivamente enviado pela OFF.IA não foram auditados.

Fontes principais:

- [README na base auditada](https://github.com/marceloroldao/memoria.ia/blob/8dd86ef37e49dfe78668a0f301302c4ab9dae43d/README.md).
- [Roadmap pós-v1](https://github.com/marceloroldao/memoria.ia/blob/8dd86ef37e49dfe78668a0f301302c4ab9dae43d/docs/ROADMAP_POST_V1.md).
- [Auditoria Python/native](https://github.com/marceloroldao/memoria.ia/blob/8dd86ef37e49dfe78668a0f301302c4ab9dae43d/docs/PYTHON_NATIVE_AUDIT.md).
- [Regressão mobile #289 e qualificação restart2](https://github.com/marceloroldao/memoria.ia/issues/289#issuecomment-5605019082).
- [Persistência EvidenceCore existente e correção do diagnóstico anterior #281](https://github.com/marceloroldao/memoria.ia/issues/281).

## 3. Diagnóstico

O projeto tem uma base implementada significativa: runtime nativo, persistência, linhagem, conceitos, relações e testes de isolamento/reinício. O gargalo imediato é demonstrar comportamento correto e reproduzível no fluxo completo da aplicação, no mesmo conjunto de versões.

Um build aprovado e uma memória persistida não provam, isoladamente, que a informação será recuperada e usada corretamente em perguntas sucessivas. O avanço funcional deve ser medido pelo ciclo completo:

`entrada → representação → persistência → consulta → pacote → prompt → resposta → validação`

### A01 — P0: recuperação repetida no aplicativo ainda sem aceite

O registro #289 mantém o aceite aberto até o reteste da OFF.IA. O último relato da tarefa “Memoria 16” informa primeira resposta correta e segunda resposta incorreta para a mesma pergunta, após restart2. Esse relato ainda precisa de reprodução instrumental; não determina sozinho qual componente falhou.

Há um teste de cinco ativações idênticas em [test_rc7_persistence_performance.py](https://github.com/marceloroldao/memoria.ia/blob/8dd86ef37e49dfe78668a0f301302c4ab9dae43d/tests/test_rc7_persistence_performance.py), mas ele usa EvidenceCore e ativação Python. Não comprova o caminho mobile completo.

No [cognitive_packet_mobile.c](https://github.com/marceloroldao/memoria.ia/blob/ef0161b8bf66f499d63bb28b816455c72e2ffdfd/native/mobile/cognitive_packet_mobile.c), `memoria_mobile_compile_context_json` chama `memoria_mobile_resolve_context_json` e empacota seu resultado. Por isso, a instrumentação deve capturar separadamente saída do resolver, pacote e prompt recebido pela LLM.

Ação: executar E1 e E2 antes de ampliar capacidades. Não declarar causa raiz como “parser”, “ativação” ou “LLM” sem a comparação.

### A02 — P1: cobertura de reinício não equivale a interrupção abrupta

O [test_cognitive_cycle_restart.py](https://github.com/marceloroldao/memoria.ia/blob/ef0161b8bf66f499d63bb28b816455c72e2ffdfd/tests/test_cognitive_cycle_restart.py) contém persistência real de EvidenceCore e reconstrução das superfícies cognitivas. Isso corrige a hipótese antiga de que essa persistência inexistia.

Entretanto, o teste real de BDR é pulado quando `BDR_ATOMIC_LIB` ou a extensão nativa não estão disponíveis. Ele também grava topologia, auditoria e evidência em operações separadas. Isso não demonstra perda de dados, mas exige testar consistência de recuperação quando o processo termina entre essas gravações.

Ação: gates dedicados devem falhar se os testes BDR obrigatórios forem pulados; testar interrupções entre etapas e recuperação de um estado coerente.

### A03 — P1: qualificação e promoção precisam de referência única

O README apresenta RC7, enquanto o pacote cognitivo e restart2 estão em outra referência. Na árvore main consultada, `native/mobile/cognitive_packet_mobile.c` não aparece; ele está presente no freeze restart2.

No SHA restart2 foram consultados:
- [Android mobile ABI: sucesso](https://github.com/marceloroldao/memoria.ia/actions/runs/34373473361).
- [Experimental PR regression: sucesso](https://github.com/marceloroldao/memoria.ia/actions/runs/34373473400).
- [live-openai: falha](https://github.com/marceloroldao/memoria.ia/actions/runs/34373814419), além de outra execução com falha. A causa e a relevância para promoção não foram investigadas nesta revisão.

Portanto, “tudo verde” seria impreciso. O [workflow Android](https://github.com/marceloroldao/memoria.ia/blob/ef0161b8bf66f499d63bb28b816455c72e2ffdfd/.github/workflows/android-mobile-abi.yml) enumera bases de PR, e #289 documenta uso de PR temporário para qualificação. Já o problema antigo de filtro de #277 não deve ser repetido como atual: o workflow experimental na main consultada já aceita base main.

Ação: criar manifesto por candidato com SHA Memoria.ia, SHA BDR, SHA OFF.IA, ABI, configuração e links de todos os gates, incluindo falhas, skips e justificativas.

### A04 — P1: evolução epistemológica necessita contrato explícito

A política histórica de #280 e #156 estabelece barreiras rígidas para material gerado. A orientação mais recente do responsável pede resolução por sustentação e trajetória, sem equiparar origem a verdade/falsidade.

Ação: documentar uma decisão arquitetural versionada e testar o novo resolver em modo comparativo. Preservar candidatos e sua origem, impedir confirmação circular e distinguir reforço independente, contradição e mudança temporal. Não remover silenciosamente a proteção existente nem reescrever freezes históricos.

### A05 — P2: documentação de desempenho ficou desatualizada

PYTHON_NATIVE_AUDIT.md ainda descreve o gargalo de 10 mil memórias como trabalho em #110. A [conclusão de #110](https://github.com/marceloroldao/memoria.ia/issues/110#issuecomment-5465621391) registra correção integrada e redução histórica do p95 de aproximadamente 710,630 ms para 6,391 ms no benchmark controlado.

Isso é uma inconsistência documental confirmada, não um gargalo atual reproduzido. O resultado histórico também não garante desempenho do pacote cognitivo atual nem do aparelho Android.

Ação: reconciliar documentação com a conclusão de #110 e medir o candidato funcional completo, evitando reimplementar a otimização já realizada.

### A06 — P2: serialização do pacote merece testes de contrato

O wrapper mobile usa busca textual de chaves JSON (`strstr`) e capacidade fixa de 32768 bytes. A leitura estática não comprova uma exploração ou falha observável, mas justifica testes com chaves repetidas em níveis diferentes, strings escapadas, Unicode, valores vazios e limites de tamanho.

Ação: provar seleção correta dos campos e erro explícito sem saída parcial; avaliar reutilização de parser estruturado existente antes de criar outro.

### A07 — P1: roadmap amplo precisa de critérios de produto

ROADMAP_POST_V1.md já define fases A–H, e testes como [test_semantic_concepts.py](https://github.com/marceloroldao/memoria.ia/blob/8dd86ef37e49dfe78668a0f301302c4ab9dae43d/tests/test_semantic_concepts.py) mostram que identidade/aliases/ambiguidade não começam do zero.

Ação: classificar cada capacidade como implementada, coberta por teste, qualificada em CI, validada no aparelho ou ainda proposta. Evitar tratar todo roadmap como pendente ou todo teste como funcionalidade plenamente aceita.

## 4. Definição de “realmente funcional”

Para o primeiro candidato de uso controlado, exigir:

1. Aprender informações dentro do contrato suportado, explicar o que foi ou não estruturado e recuperar sem depender do histórico volátil da LLM.
2. Repetir consultas sob o mesmo estado, política, escopo e relógio controlado sem variar os fatos selecionados ou reforçá-los pela leitura.
3. Preservar informações e linhagem após encerramento completo, reinício, backup/restauração e migração suportada.
4. Responder sobre estado atual, passado e mudanças sem apagar o histórico.
5. Tratar ambiguidade como pendência explícita e impedir vazamento entre usuários/aplicações.
6. Manter hipóteses e contradições rastreáveis, sem transformar ecos da mesma fonte em consenso.
7. Funcionar offline no núcleo e manter o mesmo estado ao trocar a LLM.
8. Publicar evidências do candidato exato e limites medidos no hardware-alvo.

## 5. Sequência de evolução por dependência

As metas quantitativas abaixo são propostas de aceite, não resultados já obtidos. Preservar o roadmap existente como visão de longo prazo; esta sequência define a prioridade operacional.

| Etapa | Entrega | Dependência | Critério de saída |
| --- | --- | --- | --- |
| E0 — referência reproduzível | Manifesto do candidato e matriz de capacidades | Nenhuma | SHAs, ABI, BDR, configurações, comandos, gates e limitações rastreáveis |
| E1 — recuperação determinística | Fixture sem LLM e diagnóstico resolver/pacote | E0 | 100 consultas equivalentes por cenário, sem mudança factual por leitura; antes/depois de 10 reinícios |
| E2 — integração OFF.IA | Captura pacote/prompt/resposta e aceite no aparelho | E1 | Respostas apoiadas no pacote, teste sem janela viva e sem alternância inexplicada |
| E3 — persistência e recuperação | Falhas entre gravações, backup, migração, concorrência | E1; completar com E2 | Estado coerente após interrupções; isolamento, idempotência e histórico preservados |
| E4 — resolução por evidências | Decisão arquitetural e implementação comparativa | E1 e E3 | Convergência independente; cópias não contam como novas fontes; contradição e transição distintas |
| E5 — generalização semântica | Entidades, aliases, correferência e relações suportadas | E4 | Corpus separado de desenvolvimento, casos negativos e paridade mobile/servidor |
| E6 — desempenho e operação | Benchmark do fluxo completo e observabilidade | E2–E5 | Orçamentos definidos por hardware e medidos sem reduzir correção/isolamento |
| E7 — candidato funcional | Instalação limpa, upgrade, rollback e relatório de aceite | E0–E6 | Todos os gates obrigatórios passam no mesmo candidato; nenhum bloqueador P0/P1 aberto |

### E1: primeiro experimento executável

- Usar o caso de #289 como regressão e acrescentar pelo menos dois domínios independentes; nomes do exemplo ficam exclusivamente nas fixtures.
- Medir separadamente memória fixa e conversação que acrescenta respostas geradas.
- Fixar relógio/política e registrar versão do estado. Se envelhecimento for parte do contrato, testar seu efeito separadamente.
- Comparar status, IDs de memória, relações, proveniência, valores temporais e contexto factual; normalizar somente campos voláteis documentados.
- Exportar o estado antes/depois para detectar mutações factuais causadas pela leitura.
- Se resolver variar, investigar seleção/ativação/estado. Se resolver for estável e pacote variar, investigar empacotamento. Se ambos forem estáveis, seguir para prompt/LLM em E2.
- Não fechar #289 apenas porque uma única consulta passou.

### E2–E3: experiência persistente

- Testar perguntas sucessivas, tópicos intercalados, reset da janela da LLM e reabertura completa do aplicativo.
- Registrar o hash do pacote e a identificação da requisição no diagnóstico local; exportação deve remover segredos e permitir controle de dados pessoais.
- Distinguir falha de memória, montagem de prompt, geração e validação. Resposta incompatível com evidência não pode ser silenciosamente promovida.
- Introduzir falhas antes/depois de cada fronteira durável e verificar retomada consistente. Evitar confundir reconstrução no mesmo processo com teste de processo encerrado.
- Verificar isolamento entre escopos, restauração incompleta, snapshot corrompido, importação duplicada e migração entre versões suportadas.
- Reutilizar EvidenceCorePersistence e contratos existentes; não criar um segundo armazenamento de evidência.

### E4–E5: inteligência da memória

- Definir sinais de sustentação e sua explicação, sem assumir uma soma de pesos fixos como arquitetura final.
- Preservar candidatos concorrentes e encadeamento de origem; registrar decisões e sua versão.
- Comparar fonte repetida versus múltiplas fontes independentes; usuário equivocado versus observações convergentes; alteração temporal versus contradição simultânea.
- Reaproveitar camada de conceitos existente. Adicionar referências pronominais apenas quando o contexto sustentar identidade; em ambiguidade, devolver candidatos/UNRESOLVED.
- Usar corpus de avaliação separado das frases que motivaram cada correção; medir acertos e abstinências, evitando ganhar cobertura com associações inventadas.

### E6–E7: desempenho e entrega

- Repetir 100/1k/10k registros e ampliar para 100k conforme capacidade; registrar ingestão e consulta p50/p95, RAM, disco, tempo de retomada e bytes/tokens de contexto.
- Medir memória sem LLM e latência total com LLM separadamente. Comparar contra o benchmark otimizado, não só contra o baseline antigo.
- Definir orçamento por aparelho antes do aceite; publicar hardware, dataset e configuração.
- Exigir testes nativos, BDR real sem skips obrigatórios, regressão Linux/Windows, ABI Android e aceite no dispositivo.
- Classificar a falha live-openai como bloqueadora ou integração opcional com causa e justificativa; o núcleo offline não deve depender desse serviço.
- Publicar funcionalidades suportadas e limitações. Multimodalidade ampla, aprendizado externo e MA2A seguem como expansões posteriores à base funcional.

## 6. Registro de execução e retomada

| Item | Estado em 2026-09-09 | Próxima ação |
| --- | --- | --- |
| Pedido de auditoria e documentação | Registrado neste documento | Manter referência visível no README |
| Revisão inicial | Concluída dentro do escopo da seção 2 | Expandir inspeção conforme cada etapa |
| E0 | Pendente | Eleger candidato e completar manifesto |
| E1 | Pendente | Reproduzir #289 pela ABI sem LLM |
| E2–E7 | Pendentes | Executar após dependências e atualizar evidências |
| Correção do comportamento repetido | Não comprovada por esta auditoria | Não anunciar resolvido sem E1/E2 |

Para cada avanço, acrescentar uma entrada com:

`data | etapa | SHA/ambiente | achado | mudança | teste/comando | resultado/artefato | pendência | próximo passo`

Ao interromper, registrar o último comando concluído, trabalho ainda não salvo, branch/SHA e próximo comando seguro. Não marcar uma etapa concluída por planejamento, existência de arquivo, build isolado ou aprovação de uma suíte diferente do caminho usado pelo produto.

Ponto de retomada desta revisão: E0 → E1. A documentação foi preparada; não houve alteração de runtime, fechamento de regressões ou novo aceite funcional.
