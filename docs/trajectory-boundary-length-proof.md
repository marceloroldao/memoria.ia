# Variação de comprimentos sem separador na origem

Continuação da ablação `4494b8a`. O leitor `checked_boundary_packet`, o motor, os seletores anteriores e OFF.IA permanecem inalterados. Este diagnóstico pergunta se variar separadamente os comprimentos das duas partes copiadas elimina a ambiguidade de corte.

## Intervenção

Origens não possuem marcador entre as partes. Quatro pares distintos cruzam comprimentos `(1,2)`, `(1,4)`, `(3,2)`, `(3,4)`; o controle usa `(2,3)` nos quatro pares. Conteúdos são distintos mesmo quando seus comprimentos coincidem. A consulta reservada tem partes de comprimentos `(2,3)` e nunca aparece como continuação observada.

Cada condição começa com três pares e uma raiz reservada isolada, recebe duas repetições, recebe o quarto par e depois uma raiz rival. A rival desloca o corte de origem em um símbolo. Há controles de contexto desconhecido, corpo desconhecido, corpo ausente e consultas concatenadas. Nenhuma anotação do avaliador entra no leitor.

Uma segunda intervenção remove apenas o marcador entre as cópias **no destino**. As origens e consultas são idênticas entre destinos separados e adjacentes, para cada condição de comprimento. Os destinos mudam nessa intervenção; entre comprimentos também mudam os payloads. Portanto não se trata da bateria anterior com destinos fixos, nem de uma comparação causal que isole apenas comprimento mantendo os bytes invariáveis.

## Resultado reproduzido

Seeds 20261123/20261124, cada um incluindo bijeção de símbolos:

| Comprimentos | Cópias no destino | Qualidade estrutural | Hipóteses corretas | Conflitos | Ausências vazias | Alvos retidos |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| fixos | separadas | 34/40 FAIL | 0/6 | 2/2 | 32/32 | 8/8 |
| variados | separadas | 34/40 FAIL | 0/6 | 2/2 | 32/32 | 8/8 |
| fixos | adjacentes | 40/40 | 6/6 | 2/2 | 32/32 | 8/8 |
| variados | adjacentes | 40/40 | 6/6 | 2/2 | 32/32 | 8/8 |
| total | | **148/160 FAIL** | **12/24** | **8/8** | **128/128** | **32/32** |

Zero falsas hipóteses únicas nesta bateria estreita. Todos os pacotes continuam `answer:null`, `qualified:false`. Contagens incluem formas correlacionadas e renomeações; não são 160 cenários semanticamente independentes. Resultados anteriores, incluindo 124/168 da ablação e 98/126 da bateria estrutural histórica, permanecem seus próprios denominadores e falhas.

## O que os cortes mostram

Com destinos separados, cada trio tem uma decomposição demonstrada compatível. No entanto, a consulta reservada enumera quatro cortes e só um encontra suporte, tanto antes como depois da variação adicional. A quarta combinação de comprimentos não elimina os três cortes sem suporte. Depois da rival, dois cortes encontram duas raízes distintas; ambas são preservadas.

Com destinos adjacentes, os quatro cortes encontram a mesma raiz antes da rival. Essa equivalência permite uma hipótese sobre a **raiz inteira** pelo leitor anterior, mas não uma decomposição única: concatenar as partes reconstrói os mesmos símbolos para qualquer corte. Variação reduz o número de alinhamentos testemunhados no primeiro trio (64 para 32), sem identificar um corte reservado. A rival introduz uma segunda raiz e suspende a hipótese única.

Repetições aumentam testemunhas/alinhamentos (separado: 1→4; adjacente fixo: 64→256; adjacente variável: 32→128), mantendo exatamente os mesmos layouts, payloads únicos e candidatos. O quarto par aumenta diversidade observada, mas ainda não resolve a consulta. Contagem de testemunhas não é voto nem confiança factual.

**A hipótese de que variação de comprimento basta foi rejeitada para este leitor e estes fixtures.** Não foi demonstrado que os cortes sem suporte sejam interpretações positivas rivais, nem que sejam impossíveis. Ausência de uma raiz observada não constitui prova de impossibilidade. Também não foi demonstrada impossibilidade para outros algoritmos ou dados.

## Próximo passo

Investigar separadamente um modelo explícito de compatibilidade entre molduras demonstradas e cortes de consulta: registrar por que um corte é sustentado, desconhecido ou contradito por uma observação. Uma decomposição única nos exemplos não autoriza excluir todas as demais na consulta. O próximo controle deve conter uma raiz rival tardia para um corte anteriormente sem suporte e um caso adjacente observacionalmente equivalente. Não transformar ausência em exclusão e não instalar uma política de resposta antes dessa avaliação.

## Reprodução e validação

```
python -m unittest discover -s tests -p test_trajectory_boundary_length_probe.py
python scripts/trajectory_boundary_length_probe.py --seed 20261123 --summary
python scripts/trajectory_boundary_length_probe.py --seed 20261124 --summary
python scripts/trajectory_boundary_length_probe.py --seed 20261124 --strict-quality
```

Sete testes novos passaram localmente: cruzamento dos comprimentos, suporte parcial, equivalência de cortes adjacentes, repetição sem voto, rival em outro corte, endereços/bijeção e baseline reservada. Cada leitura verifica restauração fria, estado de aprendizado e geração inalterados. O modo estrito retorna 1 para FAIL. Relatórios resumidos em `benchmark-results/trajectory-boundary-length-{development,reserved}.json`; sem `--summary`, o script reproduz proveniência completa, pacotes e testemunhas, com SHA256 registrado nos resumos. A CI recebe resumos para evitar logs de aproximadamente 50 MB por seed. Regressões locais dos probes e consumidores estruturais: **224 passed, 1 optional BDR skip**; `git diff --check` e compilação Python passaram. Validação remota do commit `be9d814`: os sete workflows aplicáveis passaram, incluindo [trajectory generation proof 37179757341](https://github.com/marceloroldao/memoria.ia/actions/runs/37179757341). O workflow experimental separado permaneceu pulado. Isso confirma integridade; qualidade permanece **148/160 FAIL**.
