"""Review caller-provided examples against structural gaps, without selecting truth."""
from trajectory_analogy_frame_probe import middle, occurrences


def validate_offers(offers):
    if not isinstance(offers,list) or not 1<=len(offers)<=8:
        raise ValueError('provide one to eight demonstration offers')
    identities=set(); characters=0
    for offer in offers:
        if not isinstance(offer,dict) or set(offer)-{'offer_id','examples','provenance'}:
            raise ValueError('invalid offer fields')
        identity=offer.get('offer_id'); examples=offer.get('examples'); provenance=offer.get('provenance','')
        if not isinstance(identity,str) or not identity.strip() or len(identity)>128 or identity in identities:
            raise ValueError('offer identities must be distinct nonempty strings of at most 128 characters')
        identities.add(identity)
        if not isinstance(provenance,str) or len(provenance)>256:
            raise ValueError('invalid caller supplied provenance')
        if not isinstance(examples,list) or not 1<=len(examples)<=3:
            raise ValueError('each offer requires one to three explicit examples')
        for example in examples:
            if not isinstance(example,dict) or set(example)!={'source_text','target_text'}:
                raise ValueError('examples require only source_text and target_text')
            for text in example.values():
                if not isinstance(text,str) or not text.strip() or len(text)>2000:
                    raise ValueError('example texts require one to 2000 nonempty characters')
                characters+=len(text)
    if characters>16000:
        raise ValueError('offer texts exceed 16000 characters in total')


def review_demonstrations(reading,offers):
    validate_offers(offers)
    diagnosis=reading['diagnosis']
    raw_frames={f['frame_id']:f for f in reading['raw_view']['frames']}
    findings={f['code'] for f in diagnosis['findings']}
    reviewed=[]
    for offer in offers:
        evidence=[]
        for index,example in enumerate(offer['examples']):
            source=tuple(map(ord,example['source_text'])); target=tuple(map(ord,example['target_text']))
            for item in diagnosis['frames']:
                frame=raw_frames[item['frame_id']]
                starts=occurrences(tuple(frame['source_prefix']),source)
                if len(starts)!=1: continue
                variable=middle(source[starts[0]:],tuple(frame['source_prefix']),tuple(frame['source_suffix']))
                if variable is None: continue
                missing={x['symbol'] for x in item.get('unwitnessed_symbols',[])}
                covered=sorted(missing.intersection(variable))
                if covered:
                    evidence.append(dict(code='EXPOSES_MISSING_SOURCE_SYMBOL',example_index=index,
                                         frame_id=item['frame_id'],source_symbols=covered,
                                         target_mapping_verified=False))
                excluded=any(t['status'] in ('TARGET_SUFFIX_MISMATCH','EMPTY_VALUE_SLOT') for t in item.get('target_checks',[]))
                ending=tuple(frame['target_suffix'])
                if excluded and target[-len(ending):]!=ending:
                    evidence.append(dict(code='VARIES_RESTRICTING_TARGET_ENDING',example_index=index,
                                         frame_id=item['frame_id'],observed_suffix=item['target_suffix'],
                                         relevance_verified=False))
        reviewed.append(dict(offer=offer,structural_evidence=evidence,
                             structurally_related_to_reported_gap=bool(evidence),
                             factual_correctness='NOT_EVALUATED',repair_guaranteed=False))
    return dict(format='memoria.ia-demonstration-review-v1',offers=reviewed,
                structurally_related_offer_ids=[r['offer']['offer_id'] for r in reviewed if r['structurally_related_to_reported_gap']],
                existing_feedback_requires_review='EXPLICIT_FEEDBACK_WITHHOLDS_CANDIDATES' in findings,
                existing_alternatives_require_review='MULTIPLE_OBSERVED_CANDIDATES' in findings,
                guidance='Confira a origem e a adequação dos exemplos. Relação estrutural não determina o mapa correto nem garante melhora; exemplos sem marcação também podem conter evidência nova.',
                provenance_status='CALLER_SUPPLIED_NOT_VERIFIED',offer_order_preserved=True,ranked=False,
                selected_offer_id=None,offers_recorded=False,request_dispatched=False,learning_performed=False,
                answer=None,qualified=False,selected_target=None,selection_used=False,
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED')
