#!/usr/bin/env python3
"""Scripted audit lifecycle; records claimed choices without incorporating examples."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_demonstration_review_probe import CATALOGUES,fixture_and_offers,populate
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_transform_catalogue_probe import EXPERIMENTS


def trial(library,catalogue,experiment):
    fixture,offers=fixture_and_offers(catalogue,experiment)
    scope=fixture['scope'];request=dict(scope=scope,text=fixture['queries'][0]['text'],offers=offers)
    with tempfile.TemporaryDirectory(prefix='memoria-operator-choice-') as directory:
        with FeedbackSession(library,directory) as session:
            populate(session,fixture)
            before=session.execute(dict(op='review_examples',**request))
            learning=session.execute(dict(op='history',scope=scope))
            foreign=session.execute(dict(op='history',scope='foreign'))
            opened=session.execute(dict(op='open_review',**request))
            receipt=opened['result']['event'];operations=[]
            for choice in ('select','defer','reject_all'):
                command=dict(op='record_review_decision',scope=scope,receipt_id=receipt['receipt_id'],decision_id='decision-'+choice,
                             actor_id='scripted-operator',choice=choice,offer_id='offer-a' if choice=='select' else None,
                             reason='Decisão programada para testar auditoria; não é avaliação humana.')
                saved=session.execute(command);replay=session.execute(command)
                operations.append(dict(command=command,saved=saved,replay_status=replay['result']['status']))
            audit=session.execute(dict(op='review_decisions',scope=scope))
            checks=dict(exact_review_stored=receipt['reviewed_result']==before['result'],
                        one_receipt_three_decisions=len(audit['result']['receipts'])==1 and len(audit['result']['decisions'])==3,
                        all_replays_idempotent=all(op['replay_status']=='EXACT_REPLAY' for op in operations),
                        learning_history_unchanged=session.execute(dict(op='history',scope=scope))==learning,
                        foreign_history_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign,
                        full_review_unchanged=session.execute(dict(op='review_examples',**request))==before,
                        no_incorporation=not audit['result']['offers_incorporated'] and not audit['result']['learning_performed'],
                        open_replay_no_append=session.execute(dict(op='open_review',**request))['result']['status']=='EXACT_REPLAY')
        with FeedbackSession(library,directory) as cold:
            checks['cold_audit']=cold.execute(dict(op='review_decisions',scope=scope))==audit
            checks['cold_review']=cold.execute(dict(op='review_examples',**request))==before
            checks['cold_decision_replays']=all(cold.execute(op['command'])['result']['status']=='EXACT_REPLAY' for op in operations)
            checks['cold_audit_still_equal']=cold.execute(dict(op='review_decisions',scope=scope))==audit
    return dict(catalogue=catalogue,experiment=experiment,opened_review=opened,decisions=operations,audit=audit,checks=checks)


def probe(library):
    cases=[trial(library,catalogue,experiment) for catalogue in CATALOGUES for experiment in EXPERIMENTS]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria.ia-operator-review-decision-probe-v1',cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Eight scripted audit cases with caller supplied identities and 24 decision events. Choice does not imply authenticated human action, factual truth, useful demonstration or incorporation into learning.')


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
