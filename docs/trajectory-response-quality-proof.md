# Qualidade de respostas textuais — 30/09/2026

**Gate de qualidade: FAIL nos dois lotes.** O experimento recupera respostas
observadas, mas ainda não seleciona respostas confiáveis em contextos variados.
Nenhum código do motor foi alterado nesta etapa.

## Método

`scripts/trajectory_response_quality_probe.py` cria nomes e códigos fictícios,
observa perguntas/respostas em capturas ordenadas e consulta a memória por
símbolos Unicode ou bytes UTF-8, sem normalização adicional. Os rótulos esperados
ficam no avaliador e nunca são entregues ao motor. Não há vocabulário semântico
de domínio, vínculo manual, LLM ou reinserção das saídas.

Cada lote tem dois sorteios, dois adaptadores e 56 consultas: 28 de resposta,
24 de ausência e quatro de conflito. Inclui pergunta exata, prefixo novo,
experiências envoltas em contexto, dois sujeitos, sujeito ausente, pergunta
sem relação, respostas concorrentes, pergunta sem resposta e capturas separadas.
Quatro consultas com mudança de caixa são desafios adicionais; as outras
52 compõem o gate obrigatório. O segundo lote muda nomes/códigos, mantendo
as mesmas famílias de cenários; não é uma validação em conversas reais.

Resposta correta exige saída selecionada diferente de eco, decodificação válida
e presença da resposta esperada completa. Retenção mede apenas sua presença em
algum candidato e não conta como acerto. A comparação por substring permite
contexto adicional e não avalia a correção de todos os trechos extras. Ausência
exige nenhuma seleção de resposta; conflito exige ambas as alternativas retidas
e nenhuma seleção única. Eco é tratado como ausência de resposta.

Toda consulta verifica estado inalterado e igualdade completa com a memória
reaberta, inclusive os campos normalmente excluídos da igualdade das dataclasses.

## Resultados

| Medida | Desenvolvimento 20260930 | Segundo lote 20261004 |
|---|---:|---:|
| Resposta correta e única | 8/28 | 8/28 |
| Resposta completa entre candidatos | 24/28 | 24/28 |
| Abstenção nos controles de ausência | 22/24 | 18/24 |
| Conflitos preservados sem seleção | 4/4 | 4/4 |
| Seleções indevidas em ausência | 2 | 6 |
| Seleções incorretas no desafio de caixa | 4 | 4 |
| Critérios obrigatórios satisfeitos | 34/52 | 30/52 |
| Saídas com decodificação inválida | 0 | 0 |
| Gate de qualidade | FAIL | FAIL |

A pergunta exata e a pergunta inteira com prefixo novo recuperam a resposta
única nos oito casos de cada lote. Quando as experiências têm contexto ao redor
da pergunta/resposta, o alvo permanece entre candidatos, mas outros fragmentos
competem e a seleção fica vazia. Isso não é uma resposta correta concluída.

O desafio de caixa produz fragmentos incorretos como saída única. Consultas sem
relação também evocam fragmentos conhecidos; no segundo lote isso ocorre ainda
para sujeitos ausentes. Logo, preservar ambiguidades em alguns cenários não
garante uma boa detecção de ausência em outros.

Relatórios completos, com consultas e saídas fictícias:
`benchmark-results/trajectory-response-quality-development.json` e
`benchmark-results/trajectory-response-quality-heldout.json`.

## Integridade e execução

Cinco testes do avaliador passaram: eco, seleção indevida, retenção sem seleção,
conflito e UTF-8 inválido. Ambos os lotes passaram nas verificações de leitura e
reabertura. O workflow executa esses contratos e publica o scorecard; seu sucesso
indica integridade da avaliação, **não aprovação do gate de qualidade**.

Reproduzir:

```sh
python -m unittest discover -s tests -p test_trajectory_response_quality_probe.py
python scripts/trajectory_response_quality_probe.py --seed 20260930
python scripts/trajectory_response_quality_probe.py --seed 20261004
python scripts/trajectory_response_quality_probe.py --seed 20261004 --strict-quality
```

Sem `--strict-quality`, o processo retorna zero se consegue executar e verificar
os contratos, mantendo `quality_status: FAIL` no relatório. Com a opção, falhas
de qualidade retornam código 1.

Uma primeira execução de desenvolvimento com frases maiores foi encerrada com
código 137 antes de produzir relatório; a causa não foi medida. Essa execução
não é validação. As frases foram encurtadas, mantendo cenários e parâmetros
padrão de geração, e os dois lotes acima foram executados nesse corpus. Não
foram medidos RAM, desempenho Android nem escalabilidade textual.

## Próxima direção

Investigar a especificidade estrutural da pista e a proveniência das ocorrências:
por que um trecho da consulta sustenta o destino e quais rotas aparecem somente
por sobreposição genérica. O objetivo é distinguir resposta sustentada de
fragmentos concorrentes sem escolher fatos por regras de nomes ou códigos.
As alternativas e os controles de ausência precisam continuar visíveis.

O gerador segue experimental, fora do OFF.IA. Os três controles funcionais
pessoais nativos anteriores continuam pendentes; este scorecard não os substitui.
O PR permanece rascunho.
