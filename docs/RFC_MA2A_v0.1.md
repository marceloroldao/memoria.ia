# Memoria.ia Agent-to-Agent Protocol (MA2A)

**Category:** Experimental / Standards Track Candidate  
**Status:** Draft RFC  
**Version:** 0.1  
**Date:** 2026-08-21  
**Protocol identifier:** `memoria.ia/a2a/0.1`

## Abstract

The Memoria.ia Agent-to-Agent Protocol (MA2A) is a deterministic communication protocol for autonomous agents using Resolutive Memory. Instead of exchanging natural-language prompts or conversation histories, agents exchange trajectory addresses, structured state deltas, hashes, capabilities, and reinforcement signals.

The protocol is local-first, offline-capable, transport-independent, cryptographically authenticated, and designed around strict namespace privacy boundaries.

"Zero-token-overhead" in this document means that protocol-native synchronization does not require LLM tokens to be transmitted between agents. It does not mean zero network bytes or zero computation.

`O(1)` refers only to local resolution of an already indexed trajectory when the underlying Resolutive Memory implementation provides that property. It is not a claim that network discovery, transport, cryptographic verification, persistence, semantic search, or end-to-end distributed resolution are `O(1)`.

---

# 1. Protocol Architecture and Overview

## 1.1 Design Principles

MA2A implementations MUST follow these principles:

1. **Deterministic addressing:** knowledge is addressed through canonical trajectory paths.
2. **Token-independent synchronization:** protocol-native state exchange MUST NOT require natural-language messages between LLMs.
3. **Local-first execution:** an L1 node SHOULD remain operational when L3 is unavailable.
4. **Deterministic convergence:** identical valid ordered deltas over the same initial state MUST produce the same logical result.
5. **Delta-first transport:** nodes SHOULD exchange mutations rather than complete snapshots whenever practical.
6. **Privacy by construction:** private namespaces MUST NOT cross the L1 trust boundary.
7. **Transport independence:** MA2A MUST NOT depend on a single physical transport.
8. **Offline capability:** authorized deltas MAY be journaled locally and synchronized after connectivity returns.
9. **Edge ownership:** private memory and LLM inference SHOULD remain at L1.
10. **Verifiability:** persistent state mutations MUST be attributable to an authenticated node or explicitly trusted local process.

## 1.2 Normative Language

The terms MUST, MUST NOT, REQUIRED, SHALL, SHALL NOT, SHOULD, SHOULD NOT, RECOMMENDED, MAY, and OPTIONAL are normative.

## 1.3 Topology Layers

### L1 — Local Agent Memory

L1 contains private user memory, local Resolutive Memory indexes, local inference, decision logic, cryptographic identity material, and unsynchronized local deltas.

A private trajectory such as:

```json
["user", "private", "profile", "secret"]
```

MUST NOT leave L1.

### L2 — Peer / Edge Transport

L2 provides low-latency synchronization among authorized agents. Implementations MAY use IPv6 overlay networks, VPN tunnels, LAN, Wi-Fi Direct, Bluetooth, QUIC, WebSockets, or other authenticated transports.

L2 MAY be direct peer communication or a regional edge relay.

### L3 — Central Consensus Relay

L3 provides global coordination including node discovery, global routing metadata, authorized delta ingestion, consensus, checkpoints, and global-state persistence.

L3 MUST NOT require heavy LLM inference as part of the MA2A protocol and MUST reject private namespaces.

```text
              +-----------------------+
              |       L3 GLOBAL       |
              | consensus / directory |
              +-----------+-----------+
                          |
                 authorized deltas
                          |
             +------------+------------+
             |                         |
         +---v----+                +---v----+
         | L2 Edge|                | L2 Edge|
         +---+----+                +---+----+
             |                         |
          L1 agents                 L1 agents
```

The architectural rule is:

```text
L1 computes
L2 synchronizes
L3 coordinates and persists authorized global state
```

---

# 2. Binary and JSON Frame Specification

## 2.1 Canonical Logical Frame

```ts
interface MA2AFrame {
  version: number;
  type: MessageType;
  flags: number;
  message_id: string;
  session_id: string;
  node_id: string;
  target_node_id?: string;
  sequence: number;
  timestamp_ms: number;
  trajectory?: string[];
  payload?: Record<string, unknown>;
  state_hash?: string;
  signature?: string;
}
```

`message_id` MUST uniquely identify a frame within the practical lifetime of the system. `sequence` MUST increase monotonically within an authenticated session for replay-sensitive operations.

## 2.2 Message Types

```text
0x01  DISCOVER
0x02  DISCOVER_RESP
0x03  HELLO
0x04  AUTH_CHALLENGE
0x05  AUTH_RESPONSE
0x06  CAPABILITIES
0x07  SESSION_ACCEPT
0x08  SESSION_REJECT
0x10  RESOLVE_REQ
0x11  RESOLVE_RESP
0x20  DELTA_EMIT
0x21  DELTA_ACK
0x30  REINFORCE_SIGNAL
0x40  HEARTBEAT
0x41  HEARTBEAT_ACK
0x50  STATE_CHECKPOINT
0x51  CONFLICT_NOTICE
0x52  RESYNC_REQ
0x60  GOODBYE
0x7F  ERROR
```

## 2.3 Trajectory Schema

A trajectory is an ordered tuple of UTF-8 strings.

```json
["shared", "global", "workflow", "step_01"]
```

Components MUST preserve order and MUST NOT be silently reordered.

## 2.4 Canonical Trajectory Encoding

For hashing and signatures, a trajectory SHALL use length-prefixed UTF-8 components:

```text
component_count : uint16
repeat component_count times:
    component_length : uint16
    component_utf8   : byte[component_length]
```

The trajectory identifier SHALL be:

```text
TrajectoryID = SHA256(CanonicalTrajectoryEncoding)
```

After both peers establish the mapping, a frame MAY carry only `TrajectoryID` rather than the full path.

## 2.5 Delta Payload

A delta SHOULD contain only changed factual attributes.

```json
{
  "temperature": 31.4,
  "status": "active",
  "revision": 184
}
```

Example `DELTA_EMIT`:

```json
{
  "version": 1,
  "type": "DELTA_EMIT",
  "flags": 0,
  "message_id": "0191f201-acde-7000-acde-001122334455",
  "session_id": "01J5SESSION01",
  "node_id": "agent:4db28e...",
  "target_node_id": "agent:781ac9...",
  "sequence": 481,
  "timestamp_ms": 1787288400000,
  "trajectory": ["shared", "global", "workflow", "step_01"],
  "payload": {"status": "complete"},
  "state_hash": "sha256:...",
  "signature": "ed25519:..."
}
```

## 2.6 Binary Envelope

```text
+--------------------------------------------------+
| Magic            4 bytes   "MA2A"               |
| Version          1 byte                         |
| Message Type     1 byte                         |
| Flags            2 bytes                        |
| Header Length    2 bytes                        |
| Payload Length   4 bytes                        |
| Sequence         8 bytes                        |
| Timestamp        8 bytes                        |
| Node ID Length   2 bytes                        |
| Trajectory Len   4 bytes                        |
| Node ID          variable                       |
| Trajectory       variable                       |
| Payload          variable                       |
| State Hash       32 bytes when present          |
| Signature        64 bytes when present          |
+--------------------------------------------------+
```

Multi-byte integers MUST use network byte order.

A conforming implementation MUST support canonical JSON. Binary profiles MAY negotiate CBOR, MessagePack, or another deterministic encoding.

## 2.7 Canonical Serialization

Before signing, implementations MUST produce a deterministic byte representation. JSON mode MUST use UTF-8, reject duplicate keys, use deterministic key ordering, and exclude the `signature` field from the signed bytes.

Production profiles SHOULD adopt a published canonical JSON serialization standard rather than implementation-specific rules.

---

# 3. Agent Lifecycle and Handshake Flow

## 3.1 Discovery

Agents MAY advertise:

```json
{
  "node_id": "agent:4db28e...",
  "protocol": "memoria.ia/a2a/0.1",
  "capabilities": ["resolve", "delta", "reinforce"],
  "namespaces": [
    ["shared", "global"],
    ["agent", "peer"]
  ],
  "encodings": ["json", "binary"]
}
```

Private namespaces MUST NOT be advertised. Discovery is not authentication.

## 3.2 Discovery Mechanisms

Implementations MAY use L2 multicast, mDNS-like discovery, Bluetooth advertisements, Wi-Fi Direct, IPv6 service discovery, configured peer lists, or L3 directory lookup.

## 3.3 Handshake Sequence

```text
Agent A                                  Agent B
   |                                        |
   |------------- HELLO ------------------->|
   |<--------- AUTH_CHALLENGE --------------|
   |---------- AUTH_RESPONSE -------------->|
   |<----------- CAPABILITIES --------------|
   |------------ CAPABILITIES ------------->|
   |<---------- SESSION_ACCEPT -------------|
   |                                        |
   |========= authenticated session ========|
```

The challenge MUST contain a cryptographically fresh nonce.

## 3.4 Capability Negotiation

Capabilities MAY include:

```text
resolve
delta
reinforce
checkpoint
binary-frame
json-frame
compression
offline-replay
vector-clock
edge-relay
```

A node MUST NOT invoke an optional operation the peer has not negotiated.

## 3.5 Namespace Permissions

Peers MUST establish authorized prefixes and operations such as `READ`, `WRITE`, `REINFORCE`, and `DENY`.

```json
{
  "permissions": [
    {
      "prefix": ["shared", "global"],
      "access": ["READ", "WRITE"]
    },
    {
      "prefix": ["agent", "peer"],
      "access": ["READ", "WRITE", "REINFORCE"]
    }
  ]
}
```

Negotiated permissions MUST NOT override the hard privacy boundary defined in Section 5.

## 3.6 Heartbeat and Disconnect

Active sessions SHOULD exchange `HEARTBEAT` / `HEARTBEAT_ACK` at a negotiated interval.

A node SHOULD send `GOODBYE` before intentional termination. Unexpected disconnects MUST NOT automatically invalidate already authenticated persistent deltas.

---

# 4. State Synchronization Mechanics

## 4.1 RESOLVE_REQ / RESOLVE_RESP

`RESOLVE_REQ` requests the state associated with an authorized trajectory.

```json
{
  "type": "RESOLVE_REQ",
  "trajectory": ["shared", "global", "machine", "motor_01"]
}
```

The receiver MUST validate the session, namespace authorization, trajectory syntax, and then perform local trajectory resolution.

Example response:

```json
{
  "type": "RESOLVE_RESP",
  "trajectory": ["shared", "global", "machine", "motor_01"],
  "payload": {
    "rpm": 1720,
    "state": "running"
  },
  "state_hash": "sha256:..."
}
```

A response MUST NOT disclose fields outside the requester's authorization.

## 4.2 DELTA_EMIT

For state `S_t` and delta `Delta_t`:

```text
S_(t+1) = Apply(S_t, Delta_t)
```

Example:

```json
{
  "type": "DELTA_EMIT",
  "trajectory": ["shared", "global", "machine", "motor_01"],
  "payload": {"rpm": 1750}
}
```

The complete prior state SHOULD NOT be retransmitted when a delta is sufficient.

## 4.3 Idempotency

Every persistent delta MUST have a unique `message_id`. Receiving the same authenticated delta more than once MUST apply it at most once.

## 4.4 DELTA_ACK

A successful receiver SHOULD respond with:

```json
{
  "type": "DELTA_ACK",
  "message_id": "...",
  "accepted": true,
  "resulting_state_hash": "sha256:..."
}
```

Acknowledgement confirms protocol acceptance, not global consensus.

## 4.5 REINFORCE_SIGNAL

`REINFORCE_SIGNAL` indicates repeated successful or agreed usage of an existing trajectory without resending the full payload.

```json
{
  "type": "REINFORCE_SIGNAL",
  "trajectory_id": "sha256:...",
  "weight_delta": 1,
  "context": "successful_resolution"
}
```

A reinforcement signal MUST NOT implicitly mutate factual payload attributes. Popularity or reinforcement MUST NOT automatically become factual truth.

## 4.6 Offline Synchronization

Disconnected L1 nodes MAY maintain an authorized outbound delta journal. Private deltas MUST NOT enter that journal.

Upon reconnection, authorized deltas are replayed through authenticated synchronization and conflict resolution before a new checkpoint is committed.

## 4.7 Checkpoints

Nodes SHOULD periodically compute a canonical state hash:

```text
H_t = SHA256(CanonicalState_t)
```

Equal checkpoint hashes MAY be treated as convergence for the synchronized scope. Unequal hashes SHOULD trigger reconciliation, not blind replacement.

---

# 5. Privacy and Namespace Isolation Rules

## 5.1 Namespace Classes

### Private

```json
["user", "private", "..."]
```

Private trajectories:

- MUST remain local;
- MUST NOT be transmitted;
- MUST NOT be advertised;
- MUST NOT be persisted by L2 relays;
- MUST NOT be persisted or processed by L3;
- MUST NOT be converted into outbound synchronization deltas.

### Global Shared

```json
["shared", "global", "..."]
```

These MAY be synchronized and persisted by L3 according to authentication, authorization, and conflict-resolution policy.

### Peer Scoped

```json
["agent", "peer", "..."]
```

These MAY be exchanged among authenticated peers, MAY be ephemeral, and MUST require explicit promotion before entering `shared/global`.

## 5.2 Hard Privacy Boundary

The rule is absolute:

```text
T[0] == "user" AND T[1] == "private"  =>  DROP
```

The check MUST occur before network serialization.

```text
Local Mutation
     |
     v
Namespace Guard
     |
     +---- private ----> Local persistence only
     |
     +---- allowed ----> Serialize -> Sign -> Transport
```

Encryption does not convert private-local data into transport-authorized data.

## 5.3 L3 Enforcement

L3 MUST independently reject private namespaces even when sent by an authenticated or privileged client.

Suggested error:

```json
{
  "type": "ERROR",
  "code": "NAMESPACE_FORBIDDEN"
}
```

L3 MUST NOT persist the prohibited payload.

## 5.4 Fail Closed

Unknown top-level namespaces SHOULD be denied by default unless explicitly allowed by the active protocol profile.

---

# 6. Conflict Resolution and Consistency Model

## 6.1 Consistency Model

MA2A uses a local-first, eventually convergent model for synchronizable namespaces. Immediate global linearizability is not required by the base protocol.

Applications requiring stronger consistency MAY define stricter profiles.

## 6.2 Delta Metadata

```ts
interface DeltaMetadata {
  message_id: string;
  node_id: string;
  logical_counter: number;
  timestamp_ms: number;
  trajectory_id: string;
  parent_state_hash?: string;
  resulting_state_hash?: string;
  vector_clock?: Record<string, number>;
}
```

Wall-clock timestamps MUST NOT be the sole ordering mechanism.

## 6.3 Vector Clock

Example:

```json
{
  "agent_A": 12,
  "agent_B": 7,
  "agent_C": 4
}
```

If neither vector clock causally dominates the other, the events are concurrent.

## 6.4 Deterministic Conflict Ordering

For competing scalar writes lacking a domain-specific merge rule, the base ordering precedence SHALL be:

```text
causal order
    >
logical counter
    >
timestamp
    >
node_id
    >
message_id
```

`node_id` and `message_id` are deterministic tie-breakers and do not imply semantic authority.

Applications SHOULD use domain-specific merge rules where appropriate. A set SHOULD normally be merged as a set rather than resolved through scalar last-writer-wins semantics.

## 6.5 Parent-State Verification

A delta MAY declare `parent_state_hash`. If the local current state differs from that parent, the receiver SHOULD classify the delta as stale or concurrent and MAY request missing deltas, merge, emit `CONFLICT_NOTICE`, or escalate according to policy.

## 6.6 Deterministic Replay

Given the same initial checkpoint `S0` and the same valid ordered delta sequence `(Delta_1 ... Delta_n)`, all conforming deterministic implementations MUST derive the same logical final state and canonical state hash.

This property SHOULD be part of the MA2A interoperability test suite.

---

# 7. Security, Identity, and Cryptography

## 7.1 Threat Model

MA2A MUST assume that traffic may be observed, modified, replayed, or relayed through untrusted infrastructure; peers may be malicious; clocks may drift; and identifiers may be spoofed unless cryptographically bound.

Cryptographic authentication proves origin and integrity. It does not prove factual truth.

## 7.2 Agent Identity

Persistent agents SHOULD possess an Ed25519 key pair `(SK_A, PK_A)`. Private keys MUST NOT be transmitted.

A Node ID SHOULD be cryptographically derived from or securely bound to its public key, for example:

```text
NodeID = SHA256(PK_A)
```

with an application-specific textual prefix.

## 7.3 Frame Signatures

Persistent state-changing messages MUST be digitally signed over the canonical frame representation using Ed25519.

The receiver MUST verify the signature before applying the mutation.

## 7.4 SHA-256

SHA-256 SHALL be used by the base profile for trajectory identifiers, state hashes, checkpoint hashes, and content integrity identifiers where applicable.

A hash is not an authentication mechanism by itself.

## 7.5 HMAC-SHA256

HMAC-SHA256 MAY be used when authenticated peers already share a symmetric session key. It MUST NOT replace Ed25519 where persistent origin attribution or third-party verification is required.

```text
Ed25519     -> persistent identity and signatures
HMAC-SHA256 -> optional authenticated session integrity
SHA-256     -> hashing and state/content identifiers
```

## 7.6 Session Authentication

A challenge-response exchange SHOULD sign a fresh nonce plus session context. Both sides SHOULD authenticate each other.

## 7.7 Replay Protection

Receivers MUST reject stale or duplicate authenticated state-changing frames. Replay protection SHOULD combine session identifier, message identifier, sequence number, logical counter, and bounded timestamp validation where appropriate.

## 7.8 Transport Encryption

Application signatures do not replace transport confidentiality. Deployments SHOULD use authenticated encryption such as TLS 1.3, QUIC/TLS, WireGuard-based IPv6 overlays, or equivalent secure transport.

## 7.9 Relay Security

An L2 or L3 relay MAY forward an application frame without being able to forge its origin. Relays MUST NOT replace the originating signature where end-to-end provenance is required.

## 7.10 Authorization

Authentication answers who sent a frame. Authorization answers whether that identity may perform the operation on the trajectory.

A state-changing frame SHOULD be accepted only when all relevant predicates hold:

```text
ValidSignature
AND ValidSession
AND AllowedNamespace
AND AllowedOperation
AND ValidOrdering
```

## 7.11 Security Invariant

No network capability, authentication result, administrator role, or transport encryption setting SHALL implicitly authorize transmission of:

```json
["user", "private", "..."]
```

under the MA2A base privacy model.

---

# Conformance

An implementation claiming **MA2A/0.1 Core Conformance** MUST at minimum:

1. implement canonical trajectory representation;
2. implement `RESOLVE_REQ` and `RESOLVE_RESP`;
3. implement `DELTA_EMIT` with idempotency;
4. enforce `user/private` before serialization;
5. support authorized `shared/global` synchronization;
6. support authenticated node identities;
7. verify Ed25519 signatures on persistent mutations;
8. implement SHA-256 trajectory and state hashing;
9. implement replay protection;
10. implement deterministic conflict ordering;
11. remain locally operable when L3 is unavailable;
12. reject malformed or unauthorized frames without mutating state.

A future interoperability suite SHOULD provide deterministic wire-format, signature, replay, conflict, privacy, and convergence test vectors.

---

# Protocol Summary

The intended communication path is:

```text
Human <-> Local LLM <-> Resolutive Memory <-> MA2A <-> Resolutive Memory
```

rather than:

```text
LLM <-> natural-language conversation <-> LLM
```

The central protocol principle is:

> **Agents exchange state, not conversation.**

The central privacy principle is:

> **Private memory is not merely encrypted in transit; it is excluded from the transport domain.**

---

# Status of This Specification

MA2A/0.1 is an experimental protocol specification.

Claims concerning sub-millisecond performance and `O(1)` trajectory resolution MUST be validated separately by reproducible benchmarks of the underlying Resolutive Memory implementation and MUST NOT be interpreted as end-to-end network guarantees.

Likewise, zero-token-overhead refers specifically to the absence of LLM-token exchange in protocol-native synchronization. MA2A still consumes network bandwidth, CPU time, memory, and cryptographic operations.
