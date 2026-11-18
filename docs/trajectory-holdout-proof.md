# Prova estrutural com contextos reservados

Esta prova exercita `associated_nodules` sobre endereços inteiros opacos. O
avaliador guarda o alvo esperado fora da memória; o mecanismo recebe apenas
payloads e a ordem das observações. Cada um dos 12 cenários por semente cria
um trecho de origem e um alvo com 3 a 6 endereços, presentes quatro vezes em
payloads com envoltórios diferentes. A consulta tem um envoltório ainda não
visto. Os demais endereços são sorteados de um domínio disjunto. Não existe
tokenização de palavras, marca de verdade nem vínculo de resposta informado
ao mecanismo.

Também são medidos: um terceiro trecho intercalado como distração; dois alvos
concorrentes; eventos invertidos (todos os alvos antes das origens); origens e
alvos em capturas distintas; uma consulta sem trecho conhecido; e 16 cópias
exatas de um payload anterior, mesmo com identificadores e capturas novos.
Em cada controle a memória é reconstruída a partir dos eventos previstos para
ele. Pesos e candidatos são lidos sem gravar a hipótese gerada como entrada.

## Resultados reproduzíveis

| Medida em 12 cenários | Desenvolvimento, antes | Desenvolvimento, depois | Reserva, depois |
| --- | ---: | ---: | ---: |
| Alvo limpo em primeiro | 10 | 12 | 12 |
| Alvo limpo entre os oito candidatos | 10 | 12 | 12 |
| Consulta inteira inédita | 12 | 12 | 12 |
| Alvo em primeiro com distração | 9 | 9 | 9 |
| Dois alvos conservados como alternativas | 9 | 12 | 12 |
| Peso do alvo reduzido pela distração | 10 | 12 | 12 |
| Falso candidato com ordem invertida | 0 | 0 | 0 |
| Falso candidato entre capturas separadas | 0 | 0 | 0 |
| Falso candidato para consulta sem trecho conhecido | 0 | 0 | 0 |
| Cópias exatas alteraram aprendizado ou evocação | 0 | 0 | 0 |

Desenvolvimento: `--seed 4107`; reserva: `--seed 20260927`. A reserva foi
executada pela primeira vez depois da correção motivada pelos dois erros do
lote de desenvolvimento. Ambos os lotes são pequenos, sintéticos e
determinísticos; o resultado da reserva não foi usado para ajustar a correção.

```bash
python scripts/trajectory_holdout_probe.py --seed 4107
python scripts/trajectory_holdout_probe.py --seed 20260927
python scripts/trajectory_generation_gate.py
```

A aceitação automática exige 100% do alvo limpo entre oito candidatos, da
consulta inédita, e dos controles negativos; pelo menos 80% do alvo limpo em
primeiro, de ambos os alvos mantidos e da redução de peso com distração; pelo
menos 70% do alvo em primeiro com distração. Assim, um `PASS` não equivale a
acerto perfeito. O fluxo `trajectory generation proof` executa os dois lotes
e os testes de regressão.

## Falha encontrada e limite

O trecho mais longo da consulta ativava apenas a escala mais profunda. Nos
dois casos perdidos, o alvo curto não existia naquela escala, embora estivesse
associado ao mesmo trecho na escala anterior. Agora a consulta reúne alvos das
escalas que representam o mesmo trecho. Representações repetidas de um alvo
não somam votos. O teste de regressão cobre um alvo curto sozinho e dois
alvos com comprimentos diferentes.

Ainda há três cenários com distração em cada lote nos quais outro alvo ocupa
o primeiro lugar. O prior `peso × comprimento` não é uma probabilidade de
verdade; pesos de escalas distintas tampouco estão calibrados entre si. Esta
prova mostra aprendizado estrutural e controles locais. Não mede compreensão
de frases, precisão de fatos pessoais ou integração do experimento Python com
o aplicativo Android. Essas propriedades exigem avaliações separadas.
