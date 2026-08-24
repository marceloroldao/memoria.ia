from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Iterable

from .textual import tokenize

# Small deterministic stopword set. This is deliberately not a language model.
_STOP = {
    'a','o','as','os','um','uma','uns','umas','de','do','da','dos','das','e','é','em','no','na','nos','nas',
    'meu','minha','meus','minhas','dele','dela','que','qual','quais','como','para','por','com','se','ao','aos',
    'the','a','an','of','and','is','are','in','on','my','his','her','what','which','how','to','for','with',
}
_ATTRIBUTE_MARKERS = {'cor','color','nome','name','status','estado','plano','plan','cidade','city','idade','age'}


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
    # Query coverage matters more than record length: long memories should still
    # be retrievable by short questions.
    qcoverage = len(shared) / len(q)
    return 0.50 * qcoverage + 0.30 * overlap + 0.20 * jaccard


@dataclass(frozen=True, slots=True)
class AutonomousRecord:
    memory_id: str
    text: str
    terms: tuple[str, ...]
    sequence: int
    provenance: str


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


class AutonomousTextMemoryV097:
    """Experimental deterministic autonomous text-memory boundary.

    It accepts raw text via ``observe`` and can retrieve related memories from a
    later raw-text ``query`` without caller-supplied memory keys or trajectories.
    Semantic discovery is intentionally conservative and is NOT claimed O(1).
    Exact resolved-address lookup remains a separate concern.
    """

    FORMAT = 'memoria.ia-autonomous-v097-1'

    def __init__(self, *, threshold: float = 0.42, ambiguity_margin: float = 0.04):
        self.threshold = threshold
        self.ambiguity_margin = ambiguity_margin
        self._records: dict[str, AutonomousRecord] = {}
        self._inverted: dict[str, set[str]] = {}
        self._sequence = 0

    def __len__(self) -> int:
        return len(self._records)

    def _index(self, record: AutonomousRecord) -> None:
        self._records[record.memory_id] = record
        for term in set(record.terms):
            self._inverted.setdefault(term, set()).add(record.memory_id)

    def observe(self, text: str, *, provenance: str = 'conversation') -> AutonomousRecord:
        clean = ' '.join(text.strip().split())
        terms = _terms(clean)
        if not clean or not terms:
            raise ValueError('observation must contain meaningful text')

        # Exact normalized duplicate reinforces identity instead of multiplying it.
        norm = tuple(sorted(set(terms)))
        for record in self._records.values():
            if tuple(sorted(set(record.terms))) == norm and record.text.casefold() == clean.casefold():
                return record

        self._sequence += 1
        memory_id = f'auto:{self._sequence:08d}'
        record = AutonomousRecord(memory_id, clean, terms, self._sequence, provenance)
        self._index(record)
        return record

    def _candidate_ids(self, query_terms: tuple[str, ...]) -> set[str]:
        candidates: set[str] = set()
        for term in set(query_terms):
            candidates.update(self._inverted.get(term, ()))
        return candidates

    @staticmethod
    def _relation(query_terms: tuple[str, ...], record: AutonomousRecord, score: float) -> str:
        q, r = set(query_terms), set(record.terms)
        if q == r or score >= 0.96:
            return 'same'
        if (q & _ATTRIBUTE_MARKERS) and (r & _ATTRIBUTE_MARKERS):
            return 'related'
        return 'related'

    def query(self, text: str, *, top_k: int = 3) -> AutonomousQueryResult:
        clean = ' '.join(text.strip().split())
        terms = _terms(clean)
        if not clean or not terms:
            raise ValueError('query must contain meaningful text')
        if top_k < 1:
            raise ValueError('top_k must be >= 1')

        candidate_ids = self._candidate_ids(terms)
        ranked: list[AutonomousHit] = []
        for memory_id in candidate_ids:
            record = self._records[memory_id]
            score = _score(terms, record.terms)
            if score >= self.threshold:
                ranked.append(AutonomousHit(
                    memory_id=record.memory_id,
                    text=record.text,
                    score=score,
                    relation=self._relation(terms, record, score),
                    sequence=record.sequence,
                ))
        ranked.sort(key=lambda h: (-h.score, -h.sequence, h.memory_id))

        # A very close runner-up is not discarded: returning both is safer than
        # inventing certainty and lets the caller surface possible conflict/polysemy.
        selected = ranked[:top_k]
        return AutonomousQueryResult(clean, tuple(selected), not bool(selected), len(candidate_ids))

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            'format': self.FORMAT,
            'threshold': self.threshold,
            'ambiguity_margin': self.ambiguity_margin,
            'sequence': self._sequence,
            'records': [asdict(r) for r in sorted(self._records.values(), key=lambda x: x.sequence)],
        }
        tmp = target.with_suffix(target.suffix + '.tmp')
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        tmp.replace(target)

    @classmethod
    def load(cls, path: str | Path) -> 'AutonomousTextMemoryV097':
        payload = json.loads(Path(path).read_text(encoding='utf-8'))
        if payload.get('format') != cls.FORMAT:
            raise ValueError('unsupported autonomous memory snapshot format')
        obj = cls(
            threshold=float(payload.get('threshold', 0.42)),
            ambiguity_margin=float(payload.get('ambiguity_margin', 0.04)),
        )
        for raw in payload.get('records', []):
            record = AutonomousRecord(
                memory_id=str(raw['memory_id']),
                text=str(raw['text']),
                terms=tuple(raw['terms']),
                sequence=int(raw['sequence']),
                provenance=str(raw.get('provenance', 'conversation')),
            )
            obj._index(record)
        obj._sequence = max(int(payload.get('sequence', 0)), max((r.sequence for r in obj._records.values()), default=0))
        return obj

    def records(self) -> tuple[AutonomousRecord, ...]:
        return tuple(sorted(self._records.values(), key=lambda r: r.sequence))
