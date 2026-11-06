#!/usr/bin/env python3
"""Scripted offer review protocol; record helpful and unhelpful attempts separately."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_feedback_portuguese_probe import score
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_transform_catalogue_probe import EXPERIMENTS, fixture_for


CATALOGUES = {
    'pressure':dict(attribute='pressão',units='Pa',training=('EFG','FGH','GHE'),target='HEG',unseen='REG',identity='YEG',
                    teaching='RFG',identity_teaching='YFG',absent='HHEG',generated='EGH',foreign='FHE',conflict_source='H',conflict_target='t'),
    'power':dict(attribute='potência',units='W',training=('JK','KL','LJ'),target='JL',unseen='OL',identity='XL',
                 teaching='OK',identity_teaching='XK',absent='JJL',generated='KJ',foreign='LK',conflict_source='J',conflict_target='r'),
}


def fixture_and_offers(catalogue,experiment):
    base=fixture_for(catalogue,experiment,'baseline',catalogues=CATALOGUES)
    offers=[]
    # Neutral IDs and identical provenance labels; no expected outputs or efficacy labels enter review.
    for identity,arm in (('offer-a','contrast'),('offer-b','intervention')):
        fixture=fixture_for(catalogue,experiment,arm,catalogues=CATALOGUES)
        added=fixture['rows'][fixture['intervention_start']:]
        examples=[dict(source_text=added[i]['text'],target_text=added[i+1]['text']) for i in range(0,len(added),3)]
        offers.append(dict(offer_id=identity,examples=examples,provenance='scripted observation for protocol test'))
    offers.append(dict(offer_id='offer-c',examples=[dict(source_text='Relato isolado sem vínculo.',target_text='Outro relato observado.')],
                       provenance='scripted observation for protocol test'))
    return base,offers


def populate(session,fixture):
    for row in fixture['rows']:
        session.execute(dict(op='observe',scope=fixture['scope'],**row))
    session.execute(dict(op='observe',scope='foreign',event_id='foreign-observation',text=fixture['foreign']))


def trial(library,catalogue,experiment):
    fixture,offers=fixture_and_offers(catalogue,experiment)
    scope=fixture['scope']; query=fixture['queries'][0]
    with tempfile.TemporaryDirectory(prefix='memoria-offer-review-') as directory:
        with FeedbackSession(library,directory) as session:
            populate(session,fixture)
            history=session.execute(dict(op='history',scope=scope))
            foreign_history=session.execute(dict(op='history',scope='foreign'))
            diagnosed=session.execute(dict(op='diagnose',scope=scope,text=query['text']))
            reviewed=session.execute(dict(op='review_examples',scope=scope,text=query['text'],offers=offers))
            projection=dict(reviewed['result']);review=projection.pop('example_review')
            checks=dict(diagnosis_identical=projection==diagnosed['result'],
                        history_unchanged=session.execute(dict(op='history',scope=scope))==history,
                        foreign_history_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign_history,
                        order_preserved=[x['offer']['offer_id'] for x in review['offers']]==[x['offer_id'] for x in offers],
                        no_selection=review['selected_offer_id'] is None and not review['selection_used'] and not review['ranked'],
                        no_automatic_action=not review['offers_recorded'] and not review['learning_performed'] and not review['request_dispatched'],
                        repeated_review=session.execute(dict(op='review_examples',scope=scope,text=query['text'],offers=offers))==reviewed)
        with FeedbackSession(library,directory) as cold:
            checks['cold_full_review']=cold.execute(dict(op='review_examples',scope=scope,text=query['text'],offers=offers))==reviewed
            checks['cold_history']=cold.execute(dict(op='history',scope=scope))==history
            checks['cold_foreign_history']=cold.execute(dict(op='history',scope='foreign'))==foreign_history
    attempts=[]
    # Every offer is tried in its own new memory, in input order; no score-driven choice or promotion.
    for offer in offers:
        with tempfile.TemporaryDirectory(prefix='memoria-offer-attempt-') as directory:
            with FeedbackSession(library,directory) as session:
                populate(session,fixture)
                for i,example in enumerate(offer['examples']):
                    for ending,text,kind in (('q',example['source_text'],'user_turn'),('a',example['target_text'],'user_turn'),
                                             ('barrier','Intervalo observado.','assistant_generated')):
                        session.execute(dict(op='observe',scope=scope,event_id=f'offer:{offer["offer_id"]}:{i}:{ending}',text=text,source_kind=kind))
                after=session.execute(dict(op='query',scope=scope,text=query['text']))
                controls=[dict(query=q,score=score(session.execute(dict(op='query',scope=scope,text=q['text'])),q['expected'])) for q in fixture['queries'][1:]]
                history=session.execute(dict(op='history',scope=scope))
            with FeedbackSession(library,directory) as cold:
                checks['cold_attempt:'+offer['offer_id']]=cold.execute(dict(op='query',scope=scope,text=query['text']))==after and cold.execute(dict(op='history',scope=scope))==history
        attempts.append(dict(offer_id=offer['offer_id'],after=after,score=score(after,query['expected']),controls=controls))
    return dict(catalogue=catalogue,experiment=experiment,query=query,review=reviewed,
                before_score=score(diagnosed,query['expected']),attempts=attempts,checks=checks)


def probe(library):
    trials=[trial(library,catalogue,experiment) for catalogue in CATALOGUES for experiment in EXPERIMENTS]
    checks={f'{i}:{k}':v for i,t in enumerate(trials) for k,v in t['checks'].items()}
    return dict(format='memoria.ia-demonstration-review-probe-v1',trials=trials,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Scripted protocol on two new curated catalogues. All caller-provided offers are attempted in separate memories for evaluation. Structural tags neither verify truth nor guarantee usefulness; human demonstration choice is not measured.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=probe(args.library)
    report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],checks=sum(report['checks'].values()),total=len(report['checks']),sha=report['report_content_sha256'])))
    raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__':main()
