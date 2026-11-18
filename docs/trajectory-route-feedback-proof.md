# Transferência experimental de oposição para uma moldura estrutural exata

Continuação: [oposição explícita ao conteúdo ou à moldura](trajectory-addressed-feedback-proof.md). Esse leitor separado elimina a atribuição implícita por unicidade; o experimento abaixo e seus resultados permanecem preservados.

O novo leitor `scripts/trajectory_route_feedback_probe.py` testa o efeito de uma correção fora da consulta e do conteúdo originalmente endereçados. Uma oposição explícita pode produzir uma penalização binária da moldura que recuperou a candidata, desde que exista exatamente uma moldura geradora, o recibo histórico seja reproduzível e a mesma moldura com as mesmas origens de testemunhos continue presente.

Essa é uma hipótese de atribuição de erro: uma candidata rejeitada não prova que sua moldura esteja errada. O experimento mede tanto a utilidade quanto o dano dessa hipótese. Fica desativado por padrão, sem integração à seleção factual, laboratório/console, MVP, ABI ou OFF.IA.

## Contrato da política

1. O leitor carrega os eventos de feedback persistidos e aplica suas retiradas antes de derivar penalizações. Apoio não produz penalização, não remove oposição e não qualifica conteúdo.
2. Para cada oposição ativa, reconstrói o prefixo de observações com o digest do snapshot original. Confere o digest do recibo, da leitura histórica e a identidade integral da candidata endereçada.
3. Se a candidata tinha várias molduras geradoras, registra `AMBIGUOUS_FRAME_ATTRIBUTION`; não atribui o erro automaticamente a todas elas.
4. Se tinha uma moldura, retém sua estrutura completa, ID, testemunhos e todas as origens dos payloads que participam desses testemunhos. A penalização exige igualdade exata desses elementos na leitura atual, no mesmo escopo.
5. Cada candidata atual conserva todas as molduras. Uma candidata alcançada também por uma moldura não penalizada permanece disponível. A oposição local ao seu recibo continua sendo aplicada pela política anterior.
6. Todas as candidatas, origens e evidências permanecem em `raw_view`. A retirada do evento original elimina sua contribuição à penalização, sem apagar feedback ou observações.

Não há escolha de vocabulário, nome de pessoa/objeto, resposta esperada ou referência do avaliador no aprendiz de penalizações. A identificação é de moldura exata com testemunhos, não de toda a categoria `symbol_transform` ou `literal_copy`. A candidata de outra consulta pode ter outro payload e outro texto; não precisa coincidir com a candidata inicialmente rejeitada.

O estado é derivado dos eventos persistidos a cada leitura. Não há novos pesos numéricos, otimização de custo, aprendizado incremental de representação ou garantia de eficiência. A penalização é uma política binária reversível sobre trajetórias de recuperação já aprendidas. A atribuição única é uma premissa experimental, não uma inferência causal de que a rota seja culpada.

## Bateria com consultas não endereçadas pelo feedback

Desenvolvimento `20270109` e reservado `20270110`: cinco cenários em texto legível e sob renomeação injetiva, dez experimentos por seed. Os seeds alteram exemplos lexicais; compartilham templates e não são amostras independentes de linguagem natural. As observações incluem os conteúdos isolados de uma segunda entidade; a consulta de transferência e seu payload não são alvos de feedback. A consulta não é ingerida.

Os alvos da oposição são escolhidos por endereços de origem observados ou pelo único conteúdo recuperado, nunca pela referência do avaliador. As referências só pontuam as leituras completas após as operações.

As contagens abaixo são **esperados recuperados / extras / perdas**, por consulta. A política local anterior não transfere feedback para a segunda consulta.

| Cenário | Política local | Transferência de moldura | Interpretação |
|---|---|---|---|
| Oposição à candidata extra de uma transformação | 1 / 1 / 0 | 1 / 0 / 0 | Um extra de outra entidade é suspenso pela mesma moldura |
| Oposição indevida à candidata correta | 1 / 0 / 0 | 0 / 0 / 1 | O erro do chamador se propaga para outro conteúdo correto |
| Candidata original alcançada por várias molduras | 1 / 0 / 0 | 1 / 0 / 0 | Atribuição ambígua não produz penalização de moldura |
| Segunda candidata ainda alcançada por outra moldura | 1 / 0 / 0 | 1 / 0 / 0 | Moldura não penalizada preserva a recuperação |
| Gêmeo com referência oculta diferente | 1 / 1 / 0 | 0 / 1 / 1 | Mesmas observações e correção não distinguem a outra relevância |

No primeiro caso, uma oposição ao conteúdo transformado de `drone`/`morena` afeta o conteúdo de outra entidade, `norde`, recuperado pela mesma moldura. A informação esperada de `norde` não é usada para decidir a penalização. O controle de moldura alternativa usa uma entidade cujos símbolos permanecem iguais sob aquela transformação: outra moldura continua oferecendo o mesmo conteúdo.

O gêmeo conserva observações, consulta, alvo, recibo, feedback e leitura completa idênticos ao primeiro cenário. Só a referência oculta do avaliador muda. Logo, a transferência que ajuda um contrato prejudica o outro, sem que exista uma diferença observável para o leitor. Os resultados não estabelecem compreensão semântica ou reconhecimento de intenção.

Todos os cenários conferem preservação da leitura bruta, ausência de mutação por consulta, política desativada, diferença entre consultas e payloads, reabertura e retirada. Retirar o feedback reverte a transferência, inclusive após reabrir o BDR. A retirada pode restaurar tanto um acerto quanto um extra.

## Resultados e reprodução

Ambos os seeds passaram em **119/119 verificações de integridade**. Os relatórios completos foram repetidos e comparados byte a byte. Incluem observações, recibo original, consulta de transferência, referências exclusivas do avaliador, leitura completa, molduras penalizadas/sobreviventes e scores separados.

| Relatório | Digest do conteúdo, excluindo `report_content_sha256` |
|---|---|
| `benchmark-results/trajectory-route-feedback-development.json` | `ea1a437144883024ec5125ae317e08c45399da563c5b8125841a2adaf87b3451` |
| `benchmark-results/trajectory-route-feedback-reserved.json` | `e49d16626543336948fc2c2962ac1cbe43e480576e873fc2fd560501dfdabef7` |

Passaram **95 testes locais distintos**: dez novos de penalização/transferência, 18 do laboratório/console e 67 regressões de feedback, retirada, relações entre rotas, composição e transformação. Os testes adicionais verificam mudança nas origens de um testemunho, prefixo indisponível, recibo adulterado, outra moldura na mesma categoria de rota, apoio concorrente, outro escopo e append gerado/isolado. Repetir uma ocorrência de testemunho invalida o transporte; conteúdo gerado não vira demonstração nem reforça a penalização. Compilação Python e `git diff --check` passaram.

```bash
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so PYTHONPATH=src \
python -m pytest -q tests/test_trajectory_route_feedback_probe.py

PYTHONPATH=src python scripts/trajectory_route_feedback_probe.py \
  --library build/trajectory-native/libmemoria_mobile.so \
  --seed 20270109 --output /tmp/route-feedback-development.json
```

BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. A CI inclui a suíte nova e ambos os seeds. Sua aprovação remota precisa ser conferida no commit publicado.

## Correção de integração dos testes anteriores

No commit `efeabec`, três workflows gerais falharam: `v0.96 semantic validation` (run `42144713545`), `product application credentials` (`42144713670`) e `product-alpha validation` (`42144713626`). Os logs identificaram 18 erros de setup nas suítes novas de laboratório/console: elas exigiam a biblioteca nativa em jobs que não a compilam. Não eram falhas dos testes de inferência, nem aprovação integral da CI.

As fixtures agora pulam os contratos nativos quando a biblioteca padrão está ausente e nenhum caminho foi explicitamente solicitado. Se `MEMORIA_NATIVE_LIBRARY` foi informado e o arquivo não existe, continuam falhando. O job dedicado compila o BDR fixado e informa esse caminho, portanto não pode aprovar silenciosamente ignorando os contratos.

Verificação local: sem biblioteca padrão e sem variável, as 28 instâncias de laboratório, console e transferência foram puladas; com caminho explícito inexistente, o teste escolhido falhou como esperado; com biblioteca real, todos os contratos rodaram. Os resultados históricos vermelhos são preservados; não se afirma aprovação remota retroativa.

## Limites e próximo problema

`general_learning_status=NOT_ESTABLISHED`, qualidade factual `NOT_EVALUATED`. O mecanismo transfere uma decisão do chamador para uma moldura exata; não demonstra que tenha descoberto a causa do erro. É possível prejudicar conteúdos corretos, inclusive sem feedback direto sobre eles. Novas molduras, novos exemplos ou mudanças de proveniência podem preservar ou restaurar uma candidata. Conteúdo ausente não é criado.

O leitor permanece experimental e separado dos consumidores atuais. O próximo problema é tornar a atribuição de erro explicitamente endereçada à moldura ou à evidência, distinguindo oposição ao conteúdo de oposição à trajetória. Só depois faz sentido comparar generalização para molduras diferentes ou atualizar pesos com critérios mais amplos. Os contraexemplos anteriores continuam válidos; este ensaio não autoriza seleção factual automática.
