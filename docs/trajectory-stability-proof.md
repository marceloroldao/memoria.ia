# Estabilidade estrutural de rotas recorrentes

Esta prova mede se experiências diferentes aumentam uma rota sem transformar
recorrência em verdade. O núcleo recebe somente endereços inteiros opacos,
ordem e captura. Os nomes `frequent`, `competing` e `isolated` existem apenas
no avaliador.

Em cada cenário, a mesma pista aparece em quatro contextos diferentes antes
de um destino, em dois contextos antes de outro e em um contexto antes de um
terceiro. Prefixos e sufixos mudam em todas as entradas. Depois, uma quinta
experiência diferente repete a primeira rota. O controle também grava oito
cópias exatas de um payload já conhecido.

`route_stability` expõe, para cada rota recorrente:

- peso bruto de associação;
- participação desse peso entre os candidatos visíveis;
- participação do escore estrutural que inclui o comprimento do destino;
- pares de payloads testemunhas;
- capturas independentes que testemunharam a rota.

`strongest` indica apenas uma liderança estrutural sem empate e sem
truncamento. `cross_stream_strongest` exige também pelo menos duas capturas.
Nenhum dos dois campos é usado por `generate` para declarar uma resposta. Se
duas rotas permanecem, a geração continua ambígua e `selected` fica vazio.

| Critério, por lote de 12 cenários | Desenvolvimento `9281903` | Reserva `20261001` |
| --- | ---: | ---: |
| Quatro contextos contra dois acumulam 4/2 testemunhas | 12 | 12 |
| Rota isolada não forma recorrência | 12 | 12 |
| Rota 4/2 é a liderança mensurável entre capturas | 12 | 12 |
| Ambiguidade impede seleção na geração | 12 | 12 |
| Oito cópias exatas não alteram estabilidade | 12 | 12 |
| Quinta experiência diferente aumenta a participação da rota | 12 | 12 |
| Empate 2/2 não produz liderança | 12 | 12 |
| Reabertura preserva a medição | 12 | 12 |

Executar:

```bash
python scripts/trajectory_stability_probe.py --seed 9281903
python scripts/trajectory_stability_probe.py --seed 20261001
```

No replay agregado do export real, 45 das 68 consultas inéditas possuem rotas
recorrentes, 33 têm mais de um destino e 35 possuem um primeiro colocado sem
empate. Apenas 6 primeiros colocados têm testemunhas em pelo menos duas
capturas; o máximo observado foi 5 capturas. O recuo para uma pista menor
sem relação no trecho maior mudou esses números (antes: 39, 27, 32 e 8,
respectivamente). Isso mostra por que liderança de
peso, recorrência entre capturas e seleção de resposta precisam permanecer
medidas distintas. O export tem somente um vínculo explícito e não permite
medir acurácia desses 45 casos.

O peso ainda depende do decaimento por distância e o escore de ordenação usa
um prior de comprimento do destino. Não há calibração estatística, confiança
factual, tratamento de dependência entre fontes ou integração ao OFF.IA.
