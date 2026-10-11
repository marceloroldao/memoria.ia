# Reuso da projeção de leitura — experimento do PR #374

## Comportamento

Uma sequência de consultas sem nova observação passa a reutilizar a projeção
de nódulos e relações da última hierarquia consultada. Evocação, estabilidade,
traçado de caminhos e geração usam a mesma projeção derivada. Isso reduz a
reconstrução repetida sem modificar pesos, seleção ou aprendizado.

Toda observação com ID novo invalida a projeção de sua hierarquia, inclusive
conteúdo já armazenado: essa ocorrência pode criar um par temporal, mudar o
relógio de esquecimento ou permitir um caminho com uma ocorrência intermediária
válida. Reexecutar o mesmo ID não invalida; identidade conflitante continua
rejeitada antes da alteração do estado. Observar outra hierarquia não invalida
a projeção ativa. Consultar outra hierarquia com conteúdo substitui a projeção
retida; consultas de hierarquias vazias não acumulam entradas.

Apenas uma projeção fica retida. Ela não entra no snapshot ou no estado de
aprendizado e é reconstruída após reabertura. Os resultados dependem das
observações preservadas, não da presença desse cache. Não há nova interpretação
semântica, seleção factual, LLM ou integração ao OFF.IA.

## Validação local — 30/09/2026 UTC

- 55 testes do gerador passaram, incluindo três novos controles de reuso,
  identidade, isolamento e invalidação por conteúdo reutilizado/esquecimento.
- O adaptador sintético de export, dois lotes reservados de contexto, quatro
  lotes de episódios, dois lotes online e dois lotes de estabilidade passaram.
- `scripts/trajectory_projection_probe.py` compara dez lotes de leitura sobre
  48 observações sintéticas: reconstruir em cada lote exige dez projeções;
  reutilizar exige uma. Evocação, estabilidade, caminhos, geração, snapshot e
  estado de aprendizado são idênticos. A geração após reabertura também coincide.
- Uma execução local mediu 0,036614 s descartando a projeção entre lotes e
  0,018390 s reutilizando-a, incluindo a construção inicial em ambos os casos.
  Tempos são descritivos; o gate exige paridade e contagem de reconstruções,
  sem impor limite de velocidade dependente da máquina.

## Validação remota

O [workflow dedicado](https://github.com/marceloroldao/memoria.ia/actions/runs/36663160139)
passou no commit `d2f70cb3ffdb915af3d903ef5ba7bbec13ba636a`: 55 testes do
gerador, todos os lotes sintéticos, o novo probe de projeção e 66 regressões
passaram. Um teste do backend BDR nativo opcional foi pulado. Pytest não estava
disponível localmente; esse conjunto foi confirmado nos logs da execução remota.
O probe remoto também produziu dez reconstruções contra uma, com paridade;
mediu 0,063841 s com descarte e 0,032390 s com reuso. Os seis arquivos publicados
foram verificados como byte a byte idênticos aos arquivos locais validados.

## Limites e próxima etapa

Esta prova cobre leituras repetidas no experimento Python. Não mede RAM,
Android, concorrência ou produção. Uma única projeção ainda pode ser grande;
não há armazenamento por demanda de nódulos frios nesta mudança. Ingestão
intercalada com cada consulta continua exigindo reconstrução. Medir esse caso
é necessário antes de projetar atualização incremental ou organização em
segundo plano. O PR permanece rascunho; os três gates pessoais nativos e a
integração do gerador ao OFF.IA continuam pendentes.
