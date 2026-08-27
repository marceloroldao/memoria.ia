from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Iterable
from .textual import TextContextMemory

@dataclass(frozen=True, slots=True)
class SemanticResolution:
    query:str; concept_id:str|None; score:float; margin:float; source:str
@dataclass(frozen=True, slots=True)
class DeflectionMetrics:
    total_queries:int; memory_resolved:int; fallback_calls:int
    @property
    def deflection_rate(self)->float:return 0.0 if self.total_queries==0 else self.memory_resolved/self.total_queries

class SemanticRouterV96:
    """Conservative non-neural semantic router with optional native top-two ranking."""
    def __init__(self,*,radius:int=3,threshold:float=.60,min_margin:float=.08,indexed:bool=False,use_native:bool|None=None,native_authoritative:bool=False)->None:
        if native_authoritative and indexed:raise ValueError("native_authoritative currently requires indexed=False")
        if native_authoritative and use_native is False:raise ValueError("native_authoritative requires native execution")
        self.memory=TextContextMemory(radius=radius,use_native=True if native_authoritative else use_native,mirror_python=not native_authoritative)
        self.native_authoritative=native_authoritative;self.threshold=threshold;self.min_margin=min_margin;self.indexed=indexed;self._concepts={};self._feature_to_concepts={};self._index_dirty=True;self._total_queries=0;self._memory_resolved=0;self._fallback_calls=0
    def observe(self,sentences:Iterable[str])->None:self.memory.observe_many(sentences);self._index_dirty=True
    def register_concept(self,concept_id:str,anchors:Iterable[str])->None:
        normalized={a.strip().lower() for a in anchors if a.strip()}
        if not normalized:raise ValueError("concept must have at least one anchor")
        self._concepts.setdefault(concept_id,set()).update(normalized);self.memory.register_concept(concept_id,normalized);self._index_dirty=True
    def _score(self,q,a):return max(self.memory.similarity(q,a),self.memory.unordered_similarity(q,a))
    @staticmethod
    def _profile_tokens(profile):return set() if not profile else {token for (_offset,token) in profile}
    def _rebuild_candidate_index(self):
        index={};profiles=self.memory.associator.profiles
        for cid,anchors in self._concepts.items():
            features=set()
            for anchor in anchors:features.update(self._profile_tokens(profiles.get(anchor)))
            for feature in features:index.setdefault(feature,set()).add(cid)
        self._feature_to_concepts=index;self._index_dirty=False
    def _candidate_ids(self,q):
        if not self.indexed:return set(self._concepts)
        if self._index_dirty:self._rebuild_candidate_index()
        candidates=set()
        for feature in self._profile_tokens(self.memory.associator.profiles.get(q)):candidates.update(self._feature_to_concepts.get(feature,()))
        return candidates
    def resolve_token(self,query:str)->SemanticResolution:
        q=query.strip().lower()
        if not q:raise ValueError("query must not be empty")
        if self.memory.native_enabled and not self.indexed:
            if not self._concepts:return SemanticResolution(q,None,0.0,0.0,"unresolved")
            ranked=self.memory.rank_registered(q,None,top_k=2);candidate_ids=None
        else:
            candidate_ids=self._candidate_ids(q)
            if not candidate_ids:return SemanticResolution(q,None,0.0,0.0,"unresolved")
            ranked=self.memory.rank_registered(q,candidate_ids,top_k=2)
        if ranked is None:
            ranked=[]
            for cid in candidate_ids:ranked.append((cid,max((self._score(q,a) for a in self._concepts[cid]),default=0.0)))
            ranked.sort(key=lambda item:(-item[1],item[0]));ranked=ranked[:2]
        best_id,best_score=ranked[0];second_score=ranked[1][1] if len(ranked)>1 else 0.0;margin=best_score-second_score
        if best_score>=self.threshold and margin>=self.min_margin:return SemanticResolution(q,best_id,best_score,margin,"memory")
        return SemanticResolution(q,None,best_score,margin,"unresolved")
    def resolve_or_fallback(self,query:str,fallback:Callable[[str],str|None])->SemanticResolution:
        self._total_queries+=1;direct=self.resolve_token(query)
        if direct.concept_id is not None:self._memory_resolved+=1;return direct
        self._fallback_calls+=1;cid=fallback(query);return SemanticResolution(query.strip().lower(),cid,direct.score,direct.margin,"fallback")
    def metrics(self)->DeflectionMetrics:return DeflectionMetrics(self._total_queries,self._memory_resolved,self._fallback_calls)
