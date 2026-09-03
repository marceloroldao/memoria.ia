# Post-v1 relation quality

This slice continues issue #135 after automatic episodic formation.

## Principle

A relation that depends on conversational deixis or an unresolved pronoun must not be promoted as a stable factual relation.

Examples rejected as relation roots/endpoints:

- `isso é verdade`
- `isto é importante`
- `aquilo é estranho`
- `ele é azul`
- `ela é engenheira`
- `aqui é frio`
- interrogative endpoints such as `quem`, `onde`, `como`, `quando`

Explicit compact relations remain supported:

- `sensor = active`
- `meu servidor é um atlas`
- `Minha bateria = carregada`
- `meu carro é um sedan e o motor um v8`

The objective is precision-first consolidation: missing a weak relation is preferable to storing a context-dependent fragment as a durable fact.
