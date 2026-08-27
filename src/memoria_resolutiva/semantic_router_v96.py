from __future__ import annotations
from dataclasses import dataclass
from math import sqrt
from typing import Callable, Iterable
from .textual import TextContextMemory, native_context_available, tokenize

_PHRASE_STOPWORDS = {
    "a", "ao", "aos", "as", "com", "da", "das", "de", "do", "dos", "e",
    "em", "na", "nas", "no", "nos", "o", "os", "para", "por", "sem", "um", "uma",
}

@dataclass(frozen=True, slots=True)
class SemanticResolution:
    query:str; concept_id:str|None; score:float; margin:float; source:str
@dataclass(frozen=True, slots=True)
class TextResolution:
    text:str; concept_id:str|None; score:float; margin:float; source:str; evidence:tuple[SemanticResolution,...]
@dataclass(frozen=True, slots=True)
class RelationEvidence:
    left:str; right:str; concept_id:str; offset:int; strength:float; weight:float
@dataclass(frozen=True, slots=True)
class RelationalTextResolution:
    text:str; concept_id:str|None; score:float; margin:float; source:str
    evidence:tuple[SemanticResolution,...]; relations:tuple[RelationEvidence,...]; relation_score:float
@dataclass(frozen=True, slots=True)
class DeflectionMetrics:
    total_queries:int; memory_resolved:int; fallback_calls:int
    @property
    def deflection_rate(self)->float:return 0.0 if self.total_queries==0 else self.memory_resolved/self.total_queries
@dataclass(frozen=True, slots=True)
class AdaptiveRoutingStats:
    total:int; full:int; discriminative:int; full_verify:int
    @property
    def verification_fraction(self)->float:return 0.0 if self.total==0 else self.full_verify/self.total
    @property
    def discriminative_fraction(self)->float:return 0.0 if self.total==0 else self.discriminative/self.total

class SemanticRouterV96:
    """Conservative non-neural semantic router with optional native top-two ranking."""
    def __init__(self,*,radius:int=3,threshold:float=.60,min_margin:float=.08,indexed:bool=False,use_native:bool|None=None,native_authoritative:bool|None=None)->None:
        if native_authoritative is True and indexed:raise ValueError("native_authoritative currently requires indexed=False")
        if native_authoritative is True and use_native is False:raise ValueError("native_authoritative requires native execution")
        if native_authoritative is None:authoritative=(not indexed) and (use_native is not False) and native_context_available()
        else:authoritative=native_authoritative
        self.memory=TextContextMemory(radius=radius,use_native=True if authoritative else use_native,mirror_python=not authoritative)
        self.native_authoritative=authoritative;self.threshold=threshold;self.min_margin=min_margin;self.indexed=indexed;self._concepts={};self._feature_to_concepts={};self._index_dirty=True;self._total_queries=0;self._memory_resolved=0;self._fallback_calls=0
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
    def _resolution_from_ranked(self,q,ranked):
        if not ranked:return SemanticResolution(q,None,0.0,0.0,"unresolved")
        best_id,best_score=ranked[0];second_score=ranked[1][1] if len(ranked)>1 else 0.0;margin=best_score-second_score
        if best_score>=self.threshold and margin>=self.min_margin:return SemanticResolution(q,best_id,best_score,margin,"memory")
        return SemanticResolution(q,None,best_score,margin,"unresolved")
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
        return self._resolution_from_ranked(q,ranked)
    def resolve_text(self,text:str)->TextResolution:
        normalized=text.strip().lower();tokens=tokenize(normalized)
        if not tokens:raise ValueError("text must contain at least one token")
        evidence=[];weights={}
        for token in tokens:
            if token in _PHRASE_STOPWORDS:continue
            resolution=self.resolve_token(token)
            if resolution.concept_id is None:continue
            weight=max(0.0,resolution.score)*max(0.0,resolution.margin)
            if weight<=0.0:continue
            evidence.append(resolution);weights[resolution.concept_id]=weights.get(resolution.concept_id,0.0)+weight
        if not weights:return TextResolution(normalized,None,0.0,0.0,"unresolved",tuple(evidence))
        ranked=sorted(weights.items(),key=lambda item:(-item[1],item[0]));total=sum(score for _,score in ranked)
        if total<=0:return TextResolution(normalized,None,0.0,0.0,"unresolved",tuple(evidence))
        best_id,best_weight=ranked[0];best_score=best_weight/total;second_score=(ranked[1][1]/total) if len(ranked)>1 else 0.0;margin=best_score-second_score
        if best_score>=self.threshold and margin>=self.min_margin:return TextResolution(normalized,best_id,best_score,margin,"memory",tuple(evidence))
        return TextResolution(normalized,None,best_score,margin,"unresolved",tuple(evidence))
    def resolve_text_relational(self,text:str,*,relation_window:int=3,relation_gain:float=1.0)->RelationalTextResolution:
        if relation_window<1:raise ValueError("relation_window must be >= 1")
        if relation_gain<0:raise ValueError("relation_gain must be >= 0")
        normalized=text.strip().lower();tokens=tokenize(normalized)
        if not tokens:raise ValueError("text must contain at least one token")
        evidence=[];positioned=[];weights={}
        for pos,token in enumerate(tokens):
            if token in _PHRASE_STOPWORDS:continue
            resolution=self.resolve_token(token)
            if resolution.concept_id is None:continue
            weight=max(0.0,resolution.score)*max(0.0,resolution.margin)
            if weight<=0.0:continue
            evidence.append(resolution);positioned.append((pos,resolution,weight));weights[resolution.concept_id]=weights.get(resolution.concept_id,0.0)+weight
        relations=[];relation_score=0.0
        for i in range(len(positioned)):
            left_pos,left,left_weight=positioned[i]
            for j in range(i+1,len(positioned)):
                right_pos,right,right_weight=positioned[j];offset=right_pos-left_pos
                if offset>relation_window:break
                if left.concept_id!=right.concept_id:continue
                forward=self.memory.relation_strength(left.query,right.query,offset)
                reverse=self.memory.relation_strength(right.query,left.query,-offset)
                strength=sqrt(max(0.0,forward)*max(0.0,reverse))
                if strength<=0.0:continue
                pair_weight=relation_gain*sqrt(left_weight*right_weight)*strength
                if pair_weight<=0.0:continue
                weights[left.concept_id]=weights.get(left.concept_id,0.0)+pair_weight;relation_score+=pair_weight
                relations.append(RelationEvidence(left.query,right.query,left.concept_id,offset,strength,pair_weight))
        if not weights:return RelationalTextResolution(normalized,None,0.0,0.0,"unresolved",tuple(evidence),tuple(relations),relation_score)
        ranked=sorted(weights.items(),key=lambda item:(-item[1],item[0]));total=sum(score for _,score in ranked)
        if total<=0:return RelationalTextResolution(normalized,None,0.0,0.0,"unresolved",tuple(evidence),tuple(relations),relation_score)
        best_id,best_weight=ranked[0];best_score=best_weight/total;second_score=(ranked[1][1]/total) if len(ranked)>1 else 0.0;margin=best_score-second_score
        if best_score>=self.threshold and margin>=self.min_margin:return RelationalTextResolution(normalized,best_id,best_score,margin,"memory_relational",tuple(evidence),tuple(relations),relation_score)
        return RelationalTextResolution(normalized,None,best_score,margin,"unresolved",tuple(evidence),tuple(relations),relation_score)
    def resolve_or_fallback(self,query:str,fallback:Callable[[str],str|None])->SemanticResolution:
        self._total_queries+=1;direct=self.resolve_token(query)
        if direct.concept_id is not None:self._memory_resolved+=1;return direct
        self._fallback_calls+=1;cid=fallback(query);return SemanticResolution(query.strip().lower(),cid,direct.score,direct.margin,"fallback")
    def metrics(self)->DeflectionMetrics:return DeflectionMetrics(self._total_queries,self._memory_resolved,self._fallback_calls)

class AdaptiveSemanticRouterV96(SemanticRouterV96):
    """Experimental native policy choosing full scan or discriminative pruning.

    Candidate pruning is accepted only for sufficiently separated Top-2 results.
    Ambiguous/pruned ties are verified with full scan so pruning cannot silently
    change deterministic tie resolution or abstention semantics.
    """
    def __init__(self,*,adaptive_threshold:int=512,candidate_limit:int=32,verification_epsilon:float=1e-12,**kwargs)->None:
        if adaptive_threshold<2:raise ValueError("adaptive_threshold must be >= 2")
        if candidate_limit<2:raise ValueError("candidate_limit must be >= 2")
        if verification_epsilon<0:raise ValueError("verification_epsilon must be >= 0")
        kwargs.setdefault("indexed",False);super().__init__(**kwargs)
        if self.indexed:raise ValueError("AdaptiveSemanticRouterV96 requires indexed=False")
        self.adaptive_threshold=adaptive_threshold;self.candidate_limit=candidate_limit;self.verification_epsilon=verification_epsilon
        self._last_route_mode="full";self._last_candidate_count=0;self._route_counts={"full":0,"discriminative":0,"full_verify":0}
    @property
    def last_route_mode(self)->str:return self._last_route_mode
    @property
    def last_candidate_count(self)->int:return self._last_candidate_count
    def _mark_route(self,mode:str,count:int)->None:self._last_route_mode=mode;self._last_candidate_count=count;self._route_counts[mode]+=1
    def routing_stats(self)->AdaptiveRoutingStats:
        total=sum(self._route_counts.values());return AdaptiveRoutingStats(total,self._route_counts["full"],self._route_counts["discriminative"],self._route_counts["full_verify"])
    def reset_routing_stats(self)->None:
        for key in self._route_counts:self._route_counts[key]=0
    def resolve_token(self,query:str)->SemanticResolution:
        q=query.strip().lower()
        if not q:raise ValueError("query must not be empty")
        if not self._concepts:self._mark_route("full",0);return SemanticResolution(q,None,0.0,0.0,"unresolved")
        if self.memory.native_enabled and len(self._concepts)>=self.adaptive_threshold:
            candidate_ids=self.memory.discriminative_candidates(q,self.candidate_limit)
            if candidate_ids:
                ranked=self.memory.rank_registered(q,candidate_ids,top_k=2);second=ranked[1][1] if ranked and len(ranked)>1 else 0.0;margin=(ranked[0][1]-second) if ranked else 0.0
                verify_margin=max(self.min_margin,self.verification_epsilon)
                if ranked and margin>verify_margin:self._mark_route("discriminative",len(candidate_ids));return self._resolution_from_ranked(q,ranked)
                self._mark_route("full_verify",len(candidate_ids));return super().resolve_token(q)
        self._mark_route("full",len(self._concepts));return super().resolve_token(q)
