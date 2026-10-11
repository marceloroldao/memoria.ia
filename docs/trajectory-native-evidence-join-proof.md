# Proveniência nativa junto ao pacote estrutural

Continuação de `d411fdb`. Os sete workflows aplicáveis desse commit concluíram com sucesso, incluindo o passo nativo de endereços/vínculos no run `37392941713`; o workflow condicionado de regressão experimental foi pulado. Este incremento adiciona somente diagnóstico, testes, relatórios e sua execução na CI. Motor, runtime e OFF.IA permanecem inalterados; o PR continua em rascunho.

## Contrato da ligação

As janelas reais do BDR são lidas pelo adaptador Unicode anterior, com sua validação de endereços, sequências e barreira para saída gerada. Uma reconstrução temporária conserva também os `hierarchy_id` nativos. Cada ocorrência mantém um mapa explícito entre o endereço nativo `(hierarchy_id, source_id, sequence)` e o endereço do payload estrutural. O metadado `reply_to` não entra na ingestão estrutural.

O leitor regional e o ledger de cortes anteriores executam sem alterações. O diagnóstico acrescenta uma seção de proveniência ao resultado: para cada ocorrência de cada candidato, registra se existe uma relação nativa explícita para o alvo selecionado. O pacote estrutural original é preservado integralmente. Não se escolhe, remove ou reforça candidato com esse campo.

O join valida as origens contra um novo replay dos textos brutos; uma origem atribuída a outro payload é rejeitada. Cada relação emitida deve corresponder ao `reply_to` da linha observada, ao endereço completo do alvo e ao texto bruto da fonte/grupo. Uma origem sem linha observada, uma origem gerada, uma referência divergente ou um candidato sem proveniência é rejeitado.

Os domínios de endereço são distintos: o runtime nativo tokeniza e normaliza seu texto; o motor experimental aqui usa caracteres Unicode brutos. O diagnóstico guarda ambos os endereços e os associa pela ocorrência e pelo texto observado, sem afirmar que seus hashes ou decomposições sejam iguais.

Este primeiro contrato aceita somente uma consulta exatamente igual ao texto bruto do alvo endereçado e um pacote nativo `exact_target`, completo e não qualificado. Pacotes globais, truncados, qualificados ou com vínculos que repetem a pergunta são rejeitados, pois a API agrupada omite esses ecos dos grupos. Não se afirma cobertura desses casos. A rejeição de um pacote incompleto não altera nem descarta as observações nativas.

## Contrafactual com observações iguais

Uma mesma região contém três pares que demonstram a moldura copiada, a pergunta reservada, duas alternativas estruturais concorrentes, um conteúdo fora da moldura e uma ocorrência gerada com texto igual ao de uma alternativa. Os símbolos do fixture anterior passam por uma bijeção para caracteres aceitos pelo tokenizer nativo, sem regras de vocabulário. A observação gerada permanece no BDR e é excluída do replay estrutural, incluindo sua origem, mesmo quando seu texto coincide com um payload válido.

As linhas e seus textos permanecem iguais em quatro estágios; só os vínculos explicitamente declarados mudam:

| Estágio | Candidatos estruturais | Relações explícitas para o alvo | Relações fora da moldura |
| --- | --- | --- | --- |
| sem vínculos | ambas as alternativas | nenhuma | nenhuma |
| primeiro vínculo | ambas as alternativas | primeira alternativa | nenhuma |
| vínculo rival | ambas as alternativas | ambas as alternativas | nenhuma |
| vínculo fora da moldura | ambas as alternativas | ambas e o conteúdo externo | uma |

O hash do **pacote estrutural completo é igual nos quatro estágios**. Os hashes dos pacotes com proveniência mudam quando as relações são observadas. A ausência inicial de `reply_to` não é convertida em negação de intenção, nem a proximidade da primeira alternativa gera automaticamente um vínculo.

O conteúdo ligado ao alvo que não combina com a moldura é preservado em `linked_roots_outside_structural_candidates`. Dessa forma, a moldura não veta nem apaga uma relação observada. O contrário também vale: uma relação não elimina alternativas estruturais ainda sem vínculo.

Cada estágio verifica memória, aprendizado e geração estruturais inalterados pelas leituras, janelas nativas inalteradas e igualdade do join completo após flush, fechamento e reabertura do BDR. A paridade inclui candidatos, origens, relações, raízes externas e o pacote/ledger estrutural integral.

## Resultados e limites

Seeds 20261201 e 20261202: **32/32 controles de integridade PASS em cada seed**. São renomeações correlacionadas de um fixture opaco; esse denominador não mede compreensão geral. Os seis testes novos incluem adulteração de origens, texto, alvo/região e consulta, rejeição de pacotes incompletos/qualificados, retenção de evidência externa, barreira gerada e execução real dos dois seeds com BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

As saídas continuam `answer:null`, `qualified:false`, `selection_used:false`, com qualidade factual `NOT_EVALUATED`. Um vínculo registrado comprova a relação observada, sem demonstrar a verdade do conteúdo. O endereço do episódio ainda é fornecido pelo chamador. Não se aprendeu a intenção ausente nos gêmeos anteriores: o FAIL 2/4 permanece, assim como o gate pessoal nativo 23/26 e os demais limites históricos.

Regressões locais dos probes e consumidores estruturais: **248 passed, 1 optional BDR skip**, com a biblioteca nativa fornecida e os testes novos executados. Os resumos e hashes completos dos dois seeds foram reproduzidos byte a byte em uma segunda execução. Compilação Python e `git diff --check` passaram. A CI de `6e8ef53` concluiu: os sete workflows aplicáveis passaram, incluindo o run `37394348674` com ambos os jobs de trajetória.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_native_evidence_join_probe.py
python scripts/trajectory_native_evidence_join_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261201 --summary
python scripts/trajectory_native_evidence_join_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261202 --summary
```

Resumos: `benchmark-results/trajectory-native-evidence-join-{development,reserved}.json`, com endereços, relações e hashes dos pacotes completos. Sem `--summary`, o script reproduz os pacotes/ledgers integrais. Próxima investigação: observar a mesma raiz em episódios com vínculos distintos e verificar a proveniência por ocorrência, incluindo repetições sem vínculo, sem propagar automaticamente a relação de uma ocorrência para todas as cópias do payload.
