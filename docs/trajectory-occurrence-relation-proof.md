# Mesmo payload, relações distintas por ocorrência

Continuação de `6e8ef53`. Esse commit passou nos sete workflows aplicáveis, incluindo o run `37394348674` de trajetória; o workflow condicionado de regressão experimental foi pulado. O novo incremento usa o adaptador regional e o join anteriores sem alterações. Adiciona um diagnóstico nativo, quatro testes, resumos reproduzíveis e um passo de CI. Nenhuma mudança no motor, runtime, seleção ou OFF.IA; PR permanece em rascunho.

## Conteúdo reutilizado e episódios separados

O fixture reutiliza a moldura opaca anterior e seus três pares de demonstração. Duas regiões possuem a mesma pergunta, os mesmos IDs/sequências para algumas fontes e as mesmas alternativas. Na primeira região, há três ocorrências da pergunta, em endereços distintos. A primeira alternativa aparece em **cinco ocorrências de usuário**, mas mantém um único endereço de payload estrutural. Sua cópia gerada é mantida no BDR e excluída do replay e das origens estruturais.

Todas as ocorrências são ingeridas antes dos vínculos. Os três estágios alteram somente relações explicitamente declaradas; o snapshot bruto estrutural e seu mapa de origens permanecem iguais. Os vínculos não são inferidos de proximidade, repetição ou igualdade de conteúdo.

| Alvo selecionado | Sem vínculos | Vínculos separados por episódio | Vínculo local tardio |
| --- | --- | --- | --- |
| primeira pergunta na primeira região | nenhuma relação | primeira alternativa e rival: conflito | duas ocorrências da primeira alternativa e rival: conflito |
| segunda ocorrência da pergunta nessa região | nenhuma relação | uma ocorrência da primeira alternativa | mesmo resultado completo |
| terceira ocorrência da pergunta nessa região | nenhuma relação | nenhuma relação | mesmo resultado completo |
| pergunta idêntica na outra região | nenhuma relação | uma ocorrência da primeira alternativa | mesmo resultado completo |

O vínculo tardio liga uma cópia até então sem vínculo ao primeiro alvo. Ele não altera o endereço do payload nem transforma outras cópias em respostas para esse alvo. O episódio sem vínculo continua sem relação, mesmo tendo uma continuação adjacente com o mesmo conteúdo que respondeu a outros episódios.

## Proveniência global versus evidência regional

O pacote estrutural de cada região conserva as duas alternativas e testemunhas somente das observações selecionadas naquela região. O join mostra também a proveniência global dos payloads compartilhados: uma mesma raiz pode possuir origens em outras regiões. Essas origens não são acrescentadas às testemunhas da moldura regional. O campo `explicit_reply_to_selected_target` diz apenas se **essa ocorrência** tem o vínculo registrado para **esse alvo completo**; false não declara que o conteúdo seja falso ou que jamais tenha respondido a outra pergunta.

Cada resultado mantém todas as sete origens de usuário das duas alternativas, inclusive cópias sem vínculo e origens estrangeiras, com flags diferentes conforme o endereço selecionado. A identidade usa `(hierarchy_id, source_id, sequence)`, evitando confundir fontes com ID e sequência iguais em regiões diferentes.

## Controle negativo

Um comparador somente do avaliador simula a regra incorreta: se uma raiz possui uma ocorrência ligada ao alvo, marcar todas as cópias dessa raiz como ligadas ao mesmo alvo. Essa regra produz **25 anotações de relação falsas** nas doze leituras por seed: 13 no estágio de vínculos separados e 12 após o vínculo tardio. O comparador não é instalado no join e não produz respostas. Seu resultado demonstra por que endereço de conteúdo e endereço de ocorrência precisam permanecer distintos; não é um escore de qualidade factual.

## Verificações e limites

Seeds 20261203/20261204: **64/64 controles de integridade PASS em cada seed**, em renomeações correlacionadas do mesmo fixture. Os controles verificam flags exatas, retenção das origens/alternativas, exclusão de origem gerada, reutilização de payload, isolamento das testemunhas regionais, leitura sem alteração das linhas, snapshot bruto igual entre estágios e igualdade do join completo após flush, fechamento e reabertura do BDR. As projeções regionais também têm paridade após restauração estrutural.

Os quatro testes cobrem origens distintas de conteúdo idêntico, colisão de ID/sequência entre regiões, desenho do fixture e execução real dos dois seeds, incluindo os resultados completos inalterados da outra região e do episódio sem vínculo após a adição local. O BDR usado é o fixado em `317882a00f041fc1568ff986af8016b09453f21a`.

Todas as saídas seguem `answer:null`, `qualified:false`, qualidade factual `NOT_EVALUATED`. O endereço do episódio continua explícito e fornecido pelo chamador. A ausência de vínculo não nega uma intenção que não foi observada. Mantêm-se o gate pessoal nativo 23/26, o FAIL 2/4 dos papéis ocultos e os limites anteriores de molduras/cortes. Este experimento não avalia aprendizagem autônoma de intenção nem reforço temporal do motor.

Regressões locais dos probes e consumidores estruturais: **252 passed, 1 optional BDR skip**, com os novos testes executados contra a biblioteca nativa. Os resumos e hashes completos dos dois seeds foram reproduzidos byte a byte em uma segunda execução. Compilação Python e `git diff --check` passaram. A CI deste novo incremento ainda precisa executar.

```sh
MEMORIA_NATIVE_LIBRARY=build/trajectory-native/libmemoria_mobile.so python -m unittest discover -s tests -p test_trajectory_occurrence_relation_probe.py
python scripts/trajectory_occurrence_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261203 --summary
python scripts/trajectory_occurrence_relation_probe.py --library build/trajectory-native/libmemoria_mobile.so --seed 20261204 --summary
```

Resumos: `benchmark-results/trajectory-occurrence-relation-{development,reserved}.json`. Sem `--summary`, reproduzem-se os pacotes/ledgers integrais, flags por origem e relações. Próxima investigação: quando o chamador conhece a região mas não o endereço do episódio, enumerar os alvos observados compatíveis com a consulta, conservar a ambiguidade e impedir um fallback silencioso para vínculos globais.
