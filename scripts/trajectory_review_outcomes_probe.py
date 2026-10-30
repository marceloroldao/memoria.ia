#!/usr/bin/env python3
"""Scripted before/after audits; subjective labels do not certify improvement."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_demonstration_review_probe import CATALOGUES,fixture_and_offers,populate
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_transform_catalogue_probe import EXPERIMENTS


def trial(library,catalogue,experiment,offer_index):
    fixture,offers=fixture_and_offers(catalogue,experiment)
    request=dict(scope=fixture['scope'],text=fixture['queries'][0]['text'],offers=offers)
    scope=fixture['scope'];selected=offers[offer_index]
    with tempfile.TemporaryDirectory(prefix='memoria-review-outcome-') as directory:
        with FeedbackSession(library,directory) as session:
            populate(session,fixture)
            before=session.execute(dict(op='open_review',**request))
            decision=session.execute(dict(op='record_review_decision',scope=scope,receipt_id=before['result']['event']['receipt_id'],
                        decision_id='scripted-choice',actor_id='scripted-operator',choice='select',offer_id=selected['offer_id'],
                        reason='Escolha programada para validar o protocolo; não é avaliação humana.'))
            # Incorporation is explicit in the evaluator, never performed by decision/outcome recording.
            for i,example in enumerate(selected['examples']):
                for ending,text,kind in (('q',example['source_text'],'user_turn'),('a',example['target_text'],'user_turn'),
                                         ('barrier','Intervalo observado.','assistant_generated')):
                    session.execute(dict(op='observe',scope=scope,event_id=f'applied-{i}-{ending}',text=text,source_kind=kind))
            after=session.execute(dict(op='open_review',**request))
            learning=session.execute(dict(op='history',scope=scope));foreign=session.execute(dict(op='history',scope='foreign'))
            reading=session.execute(dict(op='review_examples',**request))
            command=dict(op='record_review_outcome',scope=scope,decision_id='scripted-choice',after_receipt_id=after['result']['event']['receipt_id'],
                         outcome_id='scripted-outcome',actor_id='scripted-operator',judgement='helped' if offer_index==1 else 'unchanged',
                         reason='Rótulo programado do cenário, sem certificação de utilidade humana ou verdade.')
            saved=session.execute(command);replay=session.execute(command)
            audit=session.execute(dict(op='review_outcomes',scope=scope))
            comparison=saved['result']['event']['comparison']
            checks=dict(exact_decision_reference=saved['result']['event']['decision_sha256']==fingerprint(dict(address=decision['result']['address'],event=decision['result']['event'])),
                        one_outcome=len(audit['result']['outcomes'])==1,
                        idempotent_replay=replay['result']['status']=='EXACT_REPLAY',
                        learning_history_unchanged=session.execute(dict(op='history',scope=scope))==learning,
                        foreign_history_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign,
                        full_review_unchanged=session.execute(dict(op='review_examples',**request))==reading,
                        no_quality_or_causal_promotion=not comparison['retrieval_change_means_quality_improvement'] and comparison['causal_attribution']=='NOT_ESTABLISHED' and not comparison['offer_application_verified'])
        with FeedbackSession(library,directory) as cold:
            checks['cold_full_audit']=cold.execute(dict(op='review_outcomes',scope=scope))==audit
            checks['cold_review']=cold.execute(dict(op='review_examples',**request))==reading
            checks['cold_outcome_replay']=cold.execute(command)['result']['status']=='EXACT_REPLAY'
    return dict(catalogue=catalogue,experiment=experiment,selected_offer_id=selected['offer_id'],
                command=command,outcome=saved,audit=audit,checks=checks)


def probe(library):
    cases=[trial(library,catalogue,experiment,index) for catalogue in CATALOGUES for experiment in EXPERIMENTS for index in (0,1)]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria.ia-review-outcome-audit-probe-v1',cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Sixteen scripted attempts with explicit observation incorporation by evaluator. Outcome capture compares two stored snapshots, keeps caller labels separate, and establishes neither factual quality nor causal benefit of a real human choice.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=probe(args.library)
    report['report_content_sha256']=fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],cases=len(report['cases']),checks=sum(report['checks'].values()),
                         total=len(report['checks']),sha=report['report_content_sha256'])))
    raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__':main()
