from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from time import perf_counter

from .textual import tokenize

_STOP = {
    'a','o','as','os','um','uma','uns','umas','de','do','da','dos','das','e','é','em','no','na','nos','nas',
    'meu','minha','meus','minhas','dele','dela','que','qual','quais','como','para','por','com','se','ao','aos',
    'the','a','an','of','and','is','are','in','on','my','his','her','what','which','how','to','for','with',
}
_ATTRIBUTE_MARKERS = {'cor','color','nome','name','chama','status','estado','plano','plan','cidade','city','idade','age'}


def _terms(text: str) -> tuple[str, ...]:
    return tuple(t for t in tokenize(text) if len(t) > 1 and t not in _STOP)


def _score(query: tuple[str, ...], record: tuple[str, ...]) -> float:
    q, r = set(query), set(record)
    if not q or not r:
        return 0.0
    shared = q & r
    if not shared:
        return 0.0
    overlap = len(shared) / min(len(q), len(r))
    jaccard = len(shared) / len(q | r)
    qcoverage = len(shared) / len(q)
    return 0.50 * qcoverage + 0.30 * overlap + 0.20 * jaccard


def _facts(terms: tuple[str, ...]) -> dict[str, str]:
    facts: dict[str, str] = {}
    for i, term in enumerate(terms[:-1]):
        marker = 'nome' if term in {'chama','name'} else ('cor' if term == 'color' else term)
        if term in _ATTRIBUTE_MARKERS:
            facts[marker] = terms[i + 1]
    return facts


def _conflicts(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    fa, fb = _facts(a), _facts(b)
    return any(key in fb and fb[key] != value for key, value in fa.items())


@dataclass(frozen=True, slots=True)
class AutonomousRecord:
    memory_id: str
    text: str
    terms: tuple[str, ...]
    sequence: int
    provenance: str


@dataclass(frozen=True, slots=True)
class CoreMetrics:
    candidate_count: int
    selected_count: int
    best_score: float
    runner_up_score: float
    margin: float
    decision: str
    exact_lookup_used: bool
    semantic_discovery_latency_ms: float
    exact_lookup_latency_ms: float
    memories_created: int
    memories_reinforced: int
    memories_updated: int
    abstentions: int


@dataclass(frozen=True, slots=True)
class ObservationDecision:
    decision: str
    record: AutonomousRecord
    related_memory_ids: tuple[str, ...]
    metrics: CoreMetrics

    @property
    def memory_id(self) -> str:
        return self.record.memory_id


@dataclass(frozen=True, slots=True)
class AutonomousHit:
    memory_id: str
    text: str
    score: float
    relation: str
    sequence: int


@dataclass(frozen=True, slots=True)
class AutonomousQueryResult:
    query: str
    hits: tuple[AutonomousHit, ...]
    abstained: bool
    candidates_examined: int
    metrics: CoreMetrics


class AutonomousTextMemoryV097:
    FORMAT = 'memoria.ia-autonomous-v097-2'

    def __init__(self, *, threshold: float = 0.42, ambiguity_margin: float = 0.04):
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin
        self._records: dict[str, AutonomousRecord] = {}
        self._inverted: dict[str, set[str]] = {}
        self._sequence = 0
        self._reinforcements: dict[str, int] = {}

    def __len__(self) -> int:
        return len(self._records)

    def _index(self, record: AutonomousRecord) -> None:
        self._records[record.memory_id] = record
        for term in set(record.terms):
            self._inverted.setdefault(term, set()).add(record.memory_id)

    def _candidate_ids(self, terms: tuple[str, ...]) -> set[str]:
        candidates: set[str] = set()
        for term in set(terms):
            candidates.update(self._inverted.get(term, ()))
        return candidates

    def observe(self, text: str, *, provenance: str = 'conversation') -> ObservationDecision:
        started = perf_counter()
        clean = ' '.join(text.strip().split())
        terms = _terms(clean)
        if not clean or not terms:
            raise ValueError('observation must contain meaningful text')
        candidate_ids = self._candidate_ids(terms)
        ranked = sorted(((mid, _score(terms, self._records[mid].terms)) for mid in candidate_ids), key=lambda item: (-item[1], item[0]))
        best_score = ranked[0][1] if ranked else 0.0
        runner = ranked[1][1] if len(ranked) > 1 else 0.0
        margin = best_score - runner
        norm = tuple(sorted(set(terms)))
        for record in self._records.values():
            if tuple(sorted(set(record.terms))) == norm and record.text.casefold() == clean.casefold():
                self._reinforcements[record.memory_id] = self._reinforcements.get(record.memory_id, 0) + 1
                latency = (perf_counter() - started) * 1000.0
                metrics = CoreMetrics(len(candidate_ids), 1, 1.0, runner, 1.0-runner, 'same', False, latency, 0.0, 0, 1, 0, 0)
                return ObservationDecision('same', record, (record.memory_id,), metrics)
        related = tuple(mid for mid, score in ranked if score >= self.threshold)
        conflicts = tuple(mid for mid in related if _conflicts(terms, self._records[mid].terms))
        decision = 'conflict' if conflicts else ('related' if related else 'distinct')
        self._sequence += 1
        record = AutonomousRecord(f'auto:{self._sequence:08d}', clean, terms, self._sequence, provenance)
        self._index(record)
        latency = (perf_counter() - started) * 1000.0
        metrics = CoreMetrics(len(candidate_ids), len(related), best_score, runner, margin, decision, False, latency, 0.0, 1, 0, 0, 0)
        return ObservationDecision(decision, record, conflicts or related, metrics)

    def exact_lookup(self, memory_id: str) -> tuple[AutonomousRecord | None, CoreMetrics]:
        started = perf_counter(); record = self._records.get(memory_id); elapsed = (perf_counter() - started) * 1000.0
        metrics = CoreMetrics(0, int(record is not None), 1.0 if record else 0.0, 0.0, 1.0 if record else 0.0, 'same' if record else 'unresolved', True, 0.0, elapsed, 0, 0, 0, int(record is None))
        return record, metrics

    def query(self, text: str, *, top_k: int = 3) -> AutonomousQueryResult:
        started = perf_counter(); clean = ' '.join(text.strip().split()); terms = _terms(clean)
        if not clean or not terms: raise ValueError('query must contain meaningful text')
        if top_k < 1: raise ValueError('top_k must be >= 1')
        candidate_ids = self._candidate_ids(terms)
        scored = [(self._records[mid], _score(terms, self._records[mid].terms)) for mid in candidate_ids]
        scored = [(r,s) for r,s in scored if s >= self.threshold]
        scored.sort(key=lambda item: (-item[1], -item[0].sequence, item[0].memory_id))
        best = scored[0][1] if scored else 0.0; runner = scored[1][1] if len(scored)>1 else 0.0; margin = best-runner
        ambiguous = len(scored)>1 and margin < self.ambiguity_margin
        conflict_pair = len(scored)>1 and _conflicts(scored[0][0].terms, scored[1][0].terms)
        if not scored or (ambiguous and not conflict_pair):
            decision='unresolved'; selected=[]; abstained=True
        else:
            decision='conflict' if conflict_pair else ('same' if best>=0.96 else 'related'); selected=scored[:top_k]; abstained=False
        hits = tuple(AutonomousHit(r.memory_id,r.text,s,'conflict' if conflict_pair else ('same' if s>=0.96 else 'related'),r.sequence) for r,s in selected)
        latency=(perf_counter()-started)*1000.0
        metrics=CoreMetrics(len(candidate_ids),len(hits),best,runner,margin,decision,False,latency,0.0,0,0,0,int(abstained))
        return AutonomousQueryResult(clean,hits,abstained,len(candidate_ids),metrics)

    def save(self, path: str | Path) -> None:
        target=Path(path); target.parent.mkdir(parents=True,exist_ok=True)
        payload={'format':self.FORMAT,'threshold':self.threshold,'ambiguity_margin':self.ambiguity_margin,'sequence':self._sequence,'reinforcements':self._reinforcements,'records':[asdict(r) for r in sorted(self._records.values(),key=lambda x:x.sequence)]}
        tmp=target.with_suffix(target.suffix+'.tmp'); tmp.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n',encoding='utf-8'); tmp.replace(target)

    @classmethod
    def load(cls, path: str | Path) -> 'AutonomousTextMemoryV097':
        payload=json.loads(Path(path).read_text(encoding='utf-8'))
        if payload.get('format') != cls.FORMAT: raise ValueError('unsupported autonomous memory snapshot format')
        obj=cls(threshold=float(payload.get('threshold',0.42)),ambiguity_margin=float(payload.get('ambiguity_margin',0.04)))
        for raw in payload.get('records',[]):
            record=AutonomousRecord(str(raw['memory_id']),str(raw['text']),tuple(raw['terms']),int(raw['sequence']),str(raw.get('provenance','conversation'))); obj._index(record)
        obj._sequence=max(int(payload.get('sequence',0)),max((r.sequence for r in obj._records.values()),default=0)); obj._reinforcements={str(k):int(v) for k,v in payload.get('reinforcements',{}).items()}
        return obj

    def records(self) -> tuple[AutonomousRecord,...]:
        return tuple(sorted(self._records.values(),key=lambda r:r.sequence))
