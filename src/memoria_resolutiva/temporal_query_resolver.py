from __future__ import annotations

from dataclasses import dataclass
import re
import unicodedata

from .topological_memory import CognitiveResult, TemporalEventStore, TemporalOperator


def _key(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().strip().split())


def _contains_phrase(text: str, phrase: str) -> bool:
    if not phrase:
        return False
    pattern = r"(?<!\w)" + re.escape(phrase) + r"(?!\w)"
    return re.search(pattern, text) is not None


@dataclass(frozen=True, slots=True)
class TemporalQueryPlan:
    subject: str
    attribute: str
    operator: TemporalOperator
    value: str | None = None
    activated_addresses: tuple[str, ...] = ()
    candidate_sequences: tuple[int, ...] = ()


@dataclass(frozen=True, slots=True)
class TemporalQueryResolution:
    plan: TemporalQueryPlan
    result: CognitiveResult


class TemporalQueryResolver:
    """Deterministic NL-to-temporal-plan adapter for the experimental store.

    Operator words are language grammar. Entity, attribute and value vocabulary are
    never domain tables: candidates come exclusively from events already present in
    the addressable memory. Missing query dimensions may be inferred only when the
    surviving memory slot is unique; ambiguity fails closed.
    """

    def __init__(self, store: TemporalEventStore) -> None:
        self.store = store

    def _event_rows(self) -> tuple[tuple[object, str, str, str], ...]:
        rows: list[tuple[object, str, str, str]] = []
        for event in self.store.iter_events():
            subject = self.store.addresses.node(event.subject_address)
            attribute = self.store.addresses.node(event.attribute_address)
            value = self.store.addresses.node(event.value_address)
            if subject is None or attribute is None or value is None:
                continue
            rows.append((event, subject.canonical_value, attribute.canonical_value, value.canonical_value))
        return tuple(rows)

    @staticmethod
    def _operator(query: str) -> TemporalOperator:
        if "antes de" in query:
            return TemporalOperator.STATE_BEFORE_VALUE
        if "depois de" in query or "apos ficar" in query:
            return TemporalOperator.STATE_AFTER_VALUE
        if "ja foi" in query or "ja esteve" in query or "alguma vez" in query:
            return TemporalOperator.EXISTED_IN_HISTORY
        if "primeir" in query:
            return TemporalOperator.FIRST_STATE
        if "historico" in query or "historia" in query:
            return TemporalOperator.HISTORY
        if "o que mudou" in query or query.startswith("mudou "):
            return TemporalOperator.STATE_DIFF
        if re.search(r"\b(era|estava|tinha)\b", query):
            return TemporalOperator.PREVIOUS_STATE
        return TemporalOperator.CURRENT

    def plan(self, question: str) -> TemporalQueryPlan:
        query = _key(question)
        if not query:
            raise ValueError("question must be non-empty")
        rows = self._event_rows()
        if not rows:
            raise LookupError("temporal memory is empty")

        operator = self._operator(query)
        subjects = sorted({subject for _, subject, _, _ in rows}, key=lambda v: (-len(v), v))
        attributes = sorted({attribute for _, _, attribute, _ in rows}, key=lambda v: (-len(v), v))
        values = sorted({value for _, _, _, value in rows}, key=lambda v: (-len(v), v))

        subject_matches = [value for value in subjects if _contains_phrase(query, _key(value))]
        attribute_matches = [value for value in attributes if _contains_phrase(query, _key(value))]
        value_matches = [value for value in values if _contains_phrase(query, _key(value))]

        subject = subject_matches[0] if subject_matches else None
        attribute = attribute_matches[0] if attribute_matches else None
        value = value_matches[0] if value_matches else None

        candidates = list(rows)
        if subject is not None:
            candidates = [row for row in candidates if row[1] == subject]
        if attribute is not None:
            candidates = [row for row in candidates if row[2] == attribute]
        if value is not None and operator in {
            TemporalOperator.EXISTED_IN_HISTORY,
            TemporalOperator.STATE_BEFORE_VALUE,
            TemporalOperator.STATE_AFTER_VALUE,
        }:
            candidates = [row for row in candidates if row[3] == value]

        slots = {(row[1], row[2]) for row in candidates}
        if subject is None:
            possible = {slot[0] for slot in slots}
            if len(possible) == 1:
                subject = next(iter(possible))
        if attribute is None:
            possible = {slot[1] for slot in slots if subject is None or slot[0] == subject}
            if len(possible) == 1:
                attribute = next(iter(possible))

        if subject is None or attribute is None:
            raise LookupError("query is ambiguous: entity/attribute could not be resolved uniquely")

        slot_rows = [row for row in rows if row[1] == subject and row[2] == attribute]
        if operator in {
            TemporalOperator.EXISTED_IN_HISTORY,
            TemporalOperator.STATE_BEFORE_VALUE,
            TemporalOperator.STATE_AFTER_VALUE,
        }:
            if value is None:
                mentioned = [candidate for candidate in values if _contains_phrase(query, _key(candidate))]
                if len(mentioned) == 1:
                    value = mentioned[0]
            if value is None:
                raise LookupError(f"{operator.value} requires a resolvable value")

        subject_node = self.store.addresses.resolve("entity", subject)
        attribute_node = self.store.addresses.resolve("attribute", attribute)
        value_node = None if value is None else self.store.addresses.resolve("value", value)
        activated = tuple(
            address for address in (
                None if subject_node is None else subject_node.address,
                None if attribute_node is None else attribute_node.address,
                None if value_node is None else value_node.address,
            ) if address is not None
        )
        sequences = tuple(row[0].sequence for row in slot_rows)
        return TemporalQueryPlan(subject, attribute, operator, value, activated, sequences)

    def resolve(self, question: str) -> TemporalQueryResolution:
        plan = self.plan(question)
        result = self.store.resolve(
            plan.subject,
            plan.attribute,
            plan.operator,
            value=plan.value,
        )
        return TemporalQueryResolution(plan, result)
