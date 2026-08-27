from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from math import log2, sqrt

from .contextual import ContextAssociator

try:
    from ._core_native import ContextScorer as _NativeContextScorer
except ImportError:  # pragma: no cover
    _NativeContextScorer = None

_TOKEN_RE = re.compile(r"[\wÀ-ÿ]+", re.UNICODE)
def tokenize(text: str) -> list[str]: return [token.lower() for token in _TOKEN_RE.findall(text)]
def native_context_available() -> bool: return _NativeContextScorer is not None

@dataclass(frozen=True, slots=True)
class AmbiguityProbe:
    token: str
    alternatives: tuple[tuple[str, float], ...]
    normalized_entropy: float
    margin: float

class TextContextMemory:
    def __init__(self, radius: int = 3, *, use_native: bool | None = None, mirror_python: bool = True):
        self.associator = ContextAssociator(radius=radius)
        if use_native is True and _NativeContextScorer is None: raise RuntimeError("native contextual scorer is unavailable")
        enabled = _NativeContextScorer is not None if use_native is None else use_native
        if not mirror_python and not enabled: raise ValueError("mirror_python=False requires the native contextual scorer")
        self._mirror_python = mirror_python
        self._native = _NativeContextScorer(radius) if enabled and _NativeContextScorer is not None else None
    @property
    def native_enabled(self) -> bool: return self._native is not None
    @property
    def python_mirror_enabled(self) -> bool: return self._mirror_python
    def observe_sentence(self, sentence: str) -> None:
        tokens=tokenize(sentence)
        if tokens:
            if self._mirror_python:self.associator.observe(tokens)
            if self._native is not None:self._native.observe(tokens)
    def observe_many(self, sentences) -> None:
        for sentence in sentences:self.observe_sentence(sentence)
        if self._native is not None:self._native.prepare()
    def register_concept(self, concept_id: str, anchors) -> None:
        if self._native is not None:self._native.register_concept(concept_id, sorted(anchors))
    def similarity(self,a:str,b:str)->float:
        a,b=a.lower(),b.lower()
        return self._native.similarity(a,b) if self._native is not None else self.associator.similarity(a,b)
    def unordered_similarity(self,a:str,b:str)->float:
        a,b=a.lower(),b.lower()
        if self._native is not None:return self._native.unordered_similarity(a,b)
        pa,pb=self.associator.profiles.get(a),self.associator.profiles.get(b)
        if not pa or not pb:return 0.0
        ca,cb=Counter(),Counter()
        for (_o,t),c in pa.items():ca[t]+=c
        for (_o,t),c in pb.items():cb[t]+=c
        dot=sum(ca[t]*cb[t] for t in set(ca)&set(cb));na=sqrt(sum(v*v for v in ca.values()));nb=sqrt(sum(v*v for v in cb.values()))
        return dot/(na*nb) if na and nb else 0.0
    def relation_strength(self,left:str,right:str,offset:int)->float:
        left,right=left.lower(),right.lower()
        if offset==0:return 0.0
        if self._native is not None:return float(self._native.relation_strength(left,right,offset))
        profile=self.associator.profiles.get(left)
        if not profile:return 0.0
        total=sum(c for (o,_token),c in profile.items() if o==offset)
        if total<=0:return 0.0
        return profile.get((offset,right),0)/total
    def rank_registered(self,query:str,candidate_ids=None,top_k:int=2)->list[tuple[str,float]]|None:
        if self._native is None:return None
        ids=[] if candidate_ids is None else sorted(candidate_ids)
        return list(self._native.rank_registered(query.lower(),ids,top_k))
    def discriminative_candidates(self,query:str,limit:int)->list[str]|None:
        if self._native is None:return None
        return list(self._native.discriminative_candidates(query.lower(),limit))
    def nearest(self,token:str,top_k:int=5)->list[tuple[str,float]]:
        token=token.lower()
        if self._native is not None and not self._mirror_python:return list(self._native.nearest(token,top_k))
        return self.associator.nearest(token,top_k=top_k)
    def ambiguity_probe(self,token:str,top_k:int=5)->AmbiguityProbe:
        ranked=self.nearest(token,top_k=top_k);positive=[(n,max(0.0,s)) for n,s in ranked if s>0];total=sum(s for _,s in positive)
        if total<=0 or len(positive)<=1:entropy=0.0
        else:
            probs=[s/total for _,s in positive];raw=-sum(p*log2(p) for p in probs if p>0);entropy=raw/log2(len(probs))
        margin=ranked[0][1]-(ranked[1][1] if len(ranked)>1 else 0.0) if ranked else 0.0
        return AmbiguityProbe(token.lower(),tuple(ranked),entropy,margin)
