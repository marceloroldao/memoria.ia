# Prova de episódios entre conversas

Esta avaliação usa somente sequências de endereços inteiros opacos. Em cada
cenário, duas pistas compartilham dois símbolos e possuem partes finais
distintas. Cada pista aparece em quatro conversas independentes, seguida por
seu próprio alvo em um payload diferente. São oito capturas por cenário, com
envoltórios novos em cada entrada. As consultas usam envoltórios inéditos.
O avaliador conhece a construção dos cenários; a memória recebe apenas
payloads, ordem e identificadores de captura, sem rótulos de resposta,
vínculos manuais ou julgamento de verdade.

O teste exige que cada pista completa evoque somente o alvo observado após
ela, com quatro pares de payloads testemunhando a rota em quatro capturas.
Ao consultar apenas a parte compartilhada das pistas, os dois alvos precisam
permanecer disponíveis e `selected` deve ficar vazio. `generate` precisa
evocar o nódulo por `NODULE_RECALL` sem gravar a saída como experiência.

Em outro conjunto de capturas, um terceiro nódulo aparece **depois** do
alvo da primeira pista. Os dois nódulos ficam visíveis, sem resposta única;
como ambos têm o mesmo comprimento, a proximidade temporal dá maior peso
bruto ao primeiro. Controles invertem a ordem em cada captura, separam pistas
e alvos em capturas distintas, consultam um trecho ausente e repetem 16 vezes
um payload exato em novas capturas. As cópias não podem mudar aprendizado nem
evocação.

Há também um desafio adversarial: a pista B aparece **entre** a pista A e o
alvo A nas capturas A. Nesse arranjo, A passa a ter uma rota próxima para a
própria pista B; B também antecede tanto o alvo A quanto seu alvo B em
capturas diferentes. A avaliação sabe quais eventos foram interpostos, mas a
memória não recebe essa função. Mede-se quantas vezes B supera o alvo A e
quantas vezes o alvo A aparece na consulta de B. Essas duas medidas são
diagnósticas: `PASS` exige que os alvos permaneçam visíveis e que nenhuma
resposta única seja declarada nesse caso.

## Medições

| Critério, por lote de 12 cenários | Desenvolvimento `4169` | Reserva inicial `20260928` | Desafio reservado `20260929` |
| --- | ---: | ---: | ---: |
| Pista A identifica só o alvo A | 12 | 12 | 12 |
| Pista B identifica só o alvo B | 12 | 12 | 12 |
| Três consultas inéditas | 12 | 12 | 12 |
| Pista comum mantém as duas alternativas | 12 | 12 | 12 |
| Quatro testemunhas de capturas independentes para A | 12 | 12 | 12 |
| Geração associativa sem aprendizado da saída | 12 | 12 | 12 |
| Distração mantém o alvo mais próximo com maior peso e torna a saída ambígua | 12 | 12 | 12 |
| Alvos continuam visíveis com a pista B interposta | 12 | 12 | 12 |
| Pista interposta não produz seleção única | 12 | 12 | 12 |
| **B supera o alvo A com B interposto (diagnóstico)** | **9** | **8** | **9** |
| **Alvo A aparece para B interposta (diagnóstico)** | **12** | **12** | **12** |
| Candidato falso com ordem invertida | 0 | 0 | 0 |
| Candidato falso com capturas separadas | 0 | 0 | 0 |
| Candidato falso para pista ausente | 0 | 0 | 0 |
| Cópias exatas alteraram aprendizado ou evocação | 0 | 0 | 0 |

O lote de reserva inicial foi executado pela primeira vez após fechar os
cenários básicos. O desafio adversarial foi acrescentado depois; seu lote
reservado `20260929` foi executado pela primeira vez após a inclusão. `PASS`
exige todos os critérios positivos em todos os 12 cenários e zero em cada
controle negativo; as duas linhas diagnósticas em negrito não entram nessa
decisão. Os lotes têm a mesma topologia com comprimentos e endereços
variáveis, portanto não são 36 problemas sem relação entre si. O mesmo teste
roda no workflow `trajectory generation proof`.

```bash
python scripts/trajectory_episode_probe.py --seed 4169
python scripts/trajectory_episode_probe.py --seed 20260928
python scripts/trajectory_episode_probe.py --seed 20260929
```

Uma captura é apenas uma fronteira observacional: o teste não informa à
memória que o evento seguinte é uma resposta verdadeira. Uma pista comum ou
um evento distrator naturalmente produz alternativas. A pista B interposta
mostra um limite mais forte: as duas ligações B→A e B→B têm testemunhas reais
e podem empatar. Escolher o alvo desejado com base apenas nessas proximidades
seria inventar uma certeza que os eventos não fornecem. O mecanismo ainda não
calibra pesos entre escalas, interpreta perguntas ou fatos, nem demonstra
aprendizado multimodal a partir de áudio e imagens brutos. O experimento
Python continua fora da seleção de respostas do APK; os três controles
pessoais nativos anteriores permanecem sem solução.
