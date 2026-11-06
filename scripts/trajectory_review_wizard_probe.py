#!/usr/bin/env python3
"""Scripted terminal-controller exercise over real native storage, not human evaluation."""
import argparse
import itertools
import json
from pathlib import Path
import tempfile

from trajectory_demonstration_review_probe import fixture_and_offers,populate
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_review_wizard import ReviewWizard


SCENARIOS=(('selected_demonstration','2','u','a'),('selected_contrast','1','u','i'),
           ('deferred','d',None,'d'),('rejected','r',None,'i'))


def trial(library,catalogue,scenario,choice,origin,judgement):
    fixture,offers=fixture_and_offers(catalogue,'unseen_identity');scope=fixture['scope']
    inputs=['2',fixture['queries'][0]['text'],str(len(offers))]
    for offer in offers:
        inputs += [offer['provenance'],str(len(offer['examples']))]
        for example in offer['examples']:inputs += [example['source_text'],example['target_text']]
    inputs += [choice,'Escolha programada para validar o assistente de terminal.']
    if origin is not None:inputs.append(origin)
    inputs += [judgement,'Avaliação programada; não é resposta humana.','0']
    answers=iter(inputs);transcript=[];counter=itertools.count(1)
    def read(prompt):
        try:value=next(answers)
        except StopIteration:raise EOFError
        transcript.append(dict(prompt=prompt,scripted_input=value));return value
    def write(value):transcript.append(dict(output=value))
    with tempfile.TemporaryDirectory(prefix='memoria-review-wizard-') as directory:
        with FeedbackSession(library,directory) as session:
            populate(session,fixture)
            before=session.execute(dict(op='history',scope=scope))
            foreign=session.execute(dict(op='history',scope='foreign'))
            ReviewWizard(session,scope,'scripted-operator',read=read,write=write,new_id=lambda:f'proof-{next(counter)}').run()
            after=session.execute(dict(op='history',scope=scope))
            audit=session.execute(dict(op='review_outcomes',scope=scope))
            decisions=audit['result']['decisions'];outcomes=audit['result']['outcomes']
            choice_label='defer' if choice=='d' else 'reject_all' if choice=='r' else 'select'
            checks=dict(one_decision_one_outcome=len(decisions)==len(outcomes)==1,
                        declared_choice_preserved=decisions[0]['event']['choice']==choice_label,
                        declared_judgement_preserved=outcomes[0]['event']['judgement']=={'a':'helped','i':'unchanged','d':'uncertain'}[judgement],
                        learning_prefix_preserved=after['result']['entries'][:len(before['result']['entries'])]==before['result']['entries'],
                        no_learning_without_registration=(after==before) if origin is None else len(after['result']['entries'])==len(before['result']['entries'])+3,
                        foreign_history_unchanged=session.execute(dict(op='history',scope='foreign'))==foreign,
                        no_causal_promotion=outcomes[0]['event']['comparison']['causal_attribution']=='NOT_ESTABLISHED')
        with FeedbackSession(library,directory) as cold:
            checks['cold_audit']=cold.execute(dict(op='review_outcomes',scope=scope))==audit
            checks['cold_learning']=cold.execute(dict(op='history',scope=scope))==after
    return dict(catalogue=catalogue,scenario=scenario,transcript=transcript,audit=audit,checks=checks)


def probe(library):
    cases=[trial(library,catalogue,*scenario) for catalogue in ('pressure','power') for scenario in SCENARIOS]
    checks={f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria.ia-terminal-review-wizard-probe-v1',cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                human_evaluation_status='NOT_PERFORMED',general_learning_status='NOT_ESTABLISHED',
                limitation='Scripted input exercises the same terminal controller with native persistence and cold reopening. Does not measure human usability, correct choice or factual improvement.')


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
