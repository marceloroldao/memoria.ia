# Preparar e abrir o piloto local em Linux

O preparador verifica ferramentas, compila a biblioteca nativa e testa persistência em memória temporária antes de abrir o assistente de avaliação. Ele usa a fonte nativa da revisão local e o BDR fixado em `317882a00f041fc1568ff986af8016b09453f21a`. A compilação é feita no computador de destino, evitando depender de um binário produzido em outra distribuição.

## Verificar ferramentas

A partir da raiz do repositório:

```sh
python scripts/trajectory_operator_setup.py --check
```

São verificados Linux, Python 3.10+, Git, CMake 3.22+, compiladores C/C++ e Make. `TOOLS_AVAILABLE` indica somente que as ferramentas foram encontradas e responderam; não significa que a compilação, os headers de dependências ou a persistência já tenham sido validados.

Se uma ferramenta estiver ausente ou incompatível, o comando termina com código 2 e `BLOCKED`, mostrando qual verificação falhou. O modo `--check` não cria a pasta de build ou de avaliação. O preparador não instala pacotes de sistema, não executa sudo e não instala dependências Python. Dependências nativas adicionais, como o desenvolvimento de zlib, são verificadas pelo CMake durante a configuração; uma falha aparece no erro da preparação.

Se o CMake não estiver no PATH, indique seu executável:

```sh
python scripts/trajectory_operator_setup.py --check --cmake /caminho/para/cmake
```

## Preparar

```sh
python scripts/trajectory_operator_setup.py --work-dir ./build/operator-pilot
```

Na primeira execução, o preparador clona o repositório público do BDR em uma subpasta própria e seleciona o commit fixado. O clone exige acesso ao GitHub. Também pode usar um checkout que você já possua:

```sh
python scripts/trajectory_operator_setup.py \
  --work-dir ./build/operator-pilot \
  --bdr-root ./deps/resolutive-DB
```

Um checkout existente precisa estar limpo, na raiz exata e no commit fixado. Uma revisão diferente ou alterações locais fazem a preparação ser recusada; o script não faz reset, descarta mudanças ou muda a revisão desse checkout. As fontes nativas em `native/mobile` e `include` também precisam estar consolidadas no Git, sem mudanças pendentes.

A pasta de build deve ser nova, vazia ou já pertencer a este preparador e a esta configuração. Uma pasta existente sem seu marcador de propriedade é recusada antes de ser reivindicada, preservando seu conteúdo. A preparação não limpa diretórios arbitrários. Em caso de clone interrompido ou configuração incompatível, escolha uma pasta nova ou confira manualmente a pasta anterior.

O script configura CMake em Release, usa Make e compila somente o alvo `memoria_mobile`. Por padrão usa duas tarefas; `--jobs` aceita de uma a oito. O processo e o commit fixado são reproduzíveis, mas não há promessa de binários byte a byte idênticos entre caminhos, compiladores ou distribuições diferentes.

## Verificação temporária

Depois de compilar, o preparador abre uma memória temporária e verifica:

- registro de observação e preservação da origem gerada;
- revisão sem incorporação automática de exemplos;
- recibo, decisão adiada e resultado incerto;
- igualdade de histórico, revisão e auditoria após fechar e reabrir;
- reenvio idempotente da decisão e do resultado.

A memória temporária é removida depois da verificação. Os dados de um piloto real não são abertos durante essa fase. O relatório `operator-pilot-ready.json`, dentro da pasta de build, só recebe `READY_FOR_LOCAL_PILOT` após a compilação e todos esses controles. Uma falha nessa fase deixa `FAILED`, em vez de preservar silenciosamente um estado anterior de prontidão.

O relatório registra versões de ferramentas, revisão de origem, hashes dos lançadores, commit BDR, caminho e hash da biblioteca e resultados da verificação. Isso identifica o que foi testado; não é assinatura, autenticação ou validação de qualidade cognitiva. A revisão nativa consolidada e os hashes de arquivos de execução devem ser interpretados juntos, pois scripts Python podem estar sendo desenvolvidos na árvore de trabalho.

## Abrir o assistente

Para preparar e abrir em uma operação, com identidade e pasta de dados explícitas:

```sh
python scripts/trajectory_operator_setup.py \
  --work-dir ./build/operator-pilot \
  --run \
  --data-dir ./data/piloto-operador \
  --scope piloto_marcelo \
  --actor marcelo
```

O preparador não exige `PYTHONPATH` manual: configura o ambiente do assistente. Build e dados precisam estar em pastas separadas, sem que uma contenha a outra. `--run` exige `--data-dir` e `--actor`; a identidade continua sendo declarada, sem autenticação.

O preparo completo é revalidado antes de cada `--run`. Depois disso, o lançador abre somente a pasta de avaliação explicitamente indicada. O campo `pilot_data_opened_during_prepare=false` do relatório descreve a preparação, não a abertura posterior solicitada por `--run`.

Use o [roteiro do piloto](trajectory-operator-pilot.md) e o [guia dos menus](trajectory-review-wizard.md). Para abrir diretamente uma biblioteca já validada, o lançador anterior continua disponível. Encerrar normalmente o assistente preserva as decisões e resultados para retomada.

## Escopo da validação

Passaram **35 testes locais**, treze novos do preparador e 22 regressões do assistente e da retomada. A execução final usou a biblioteca recém-compilada, não somente o binário anterior. Os casos cobrem ferramenta ausente sem escrita, pasta de dados preservada, recusa de configuração/checkout incorretos, separação de pastas, identidade inválida antes do build, falha de configuração substituindo prontidão antiga e teste nativo temporário.

Foram feitas **duas compilações limpas reais**: uma reutilizando um checkout BDR limpo e fixado, e outra pelo clone padrão em pasta nova. Ambas passaram nas **nove verificações temporárias de persistência**. A repetição de cada build conservou o hash de sua própria biblioteca; não se afirma igualdade de binários entre caminhos diferentes. Um lançamento real por `--run`, com entrada programada para sair do menu, terminou com código 0, apresentou a mensagem de preparação antes do menu e deixou a memória de avaliação sem observações ou resultados.

O relatório consolidado está em `benchmark-results/trajectory-operator-setup-validation.json`, com versões de ferramentas, hashes dos binários e do preparador, controles de persistência e os 35 resultados de testes derivados do JUnit. Compilação Python e `git diff --check` passaram. A CI do novo incremento fica pendente após publicação.

O preparo técnico não representa uma avaliação com pessoa real. Ele não instala ou reinicia serviços, publica aplicação, muda a ABI ou valida uma versão de produção. Os controles medem inicialização e persistência do protocolo local; a avaliação cognitiva e de utilidade humana continua pendente.
