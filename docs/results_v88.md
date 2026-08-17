# memoria.ia v0.88 — Shared knowledge with route-local lifecycle

The v0.88 experiment combines shared knowledge payloads with an independent saturating lifecycle for each trajectory.

## Controlled isolation test

Two routes were registered for the same knowledge node:

- private visual route from robot-1;
- collective language route from the fleet.

Both routes received 32 coherent supports and reached active depth 4.

Then only the visual route received 24 contradictions.

Observed state:

- visual route active depth: -1
- visual route historical depth: 4
- collective route active depth: 4
- collective route historical depth: 4

After 16 new coherent supports on the visual route:

- visual route active depth returned to 4;
- collective route remained at depth 4 throughout;
- both routes continued resolving to the same shared knowledge payload.

## Interpretation

This supports the architectural claim that multinodal/multimodal routes can share semantic payload storage while preserving independent confidence/lifecycle state. A noisy or failing sensor/agent route can therefore deactivate locally without automatically deleting or weakening all other routes to the same knowledge.

The experiment does not yet solve distributed consensus or semantic identity discovery across independently created knowledge IDs. Those remain separate problems for the path to v0.90/v1.0.
