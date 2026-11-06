#!/usr/bin/env python3
"""Exercise operator diagnostics without supplying answer references."""
import argparse
import json
from pathlib import Path
import tempfile

from trajectory_feedback_case_probe import sensitive_fixture
from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_transform_catalogue_probe import ARMS, CATALOGUES, EXPERIMENTS, fixture_for


def trial(library, fixture, query, label):
    scope = fixture['scope']
    with tempfile.TemporaryDirectory(prefix='memoria-evidence-diagnosis-') as directory:
        with FeedbackSession(library,directory) as session:
            for row in fixture['rows']:
                session.execute(dict(op='observe',scope=scope,**row))
            history = session.execute(dict(op='history',scope=scope))
            plain = session.execute(dict(op='query',scope=scope,text=query))
            diagnosed = session.execute(dict(op='diagnose',scope=scope,text=query))
            projected = dict(diagnosed['result']);diagnosis = projected.pop('diagnosis')
            checks = dict(query_result_identical=projected==plain['result'],
                          history_read_only=session.execute(dict(op='history',scope=scope))==history,
                          repeated_full_diagnosis=session.execute(dict(op='diagnose',scope=scope,text=query))==diagnosed,
                          no_automatic_action=not diagnosis['request_dispatched'] and not diagnosis['learning_performed'],
                          unqualified=diagnosis['answer'] is None and diagnosis['selected_target'] is None and not diagnosis['qualified'] and not diagnosis['selection_used'],
                          transform_trace_parity=diagnosis['transform_trace']['candidate_set_equal'])
        with FeedbackSession(library,directory) as cold:
            checks['cold_full_diagnosis']=cold.execute(dict(op='diagnose',scope=scope,text=query))==diagnosed
            checks['cold_history']=cold.execute(dict(op='history',scope=scope))==history
    return dict(label=label,scope=scope,query=query,view=diagnosed,checks=checks)


def probe(library):
    cases = []
    for catalogue in CATALOGUES:
        for experiment in EXPERIMENTS:
            for arm in ARMS:
                fixture = fixture_for(catalogue,experiment,arm)
                cases.append(trial(library,fixture,fixture['queries'][0]['text'],f'{catalogue}:{experiment}:{arm}'))
    sensitive = sensitive_fixture()
    for query in sensitive['queries']:
        cases.append(trial(library,sensitive,query['text'],'sensitive:'+query['name']))
    cases.append(trial(library,dict(scope='empty',rows=[]),'Pergunta sem exemplos.','empty'))
    fixture = fixture_for('frequency','unseen_symbol','baseline')
    cases.append(trial(library,fixture,'zzzzzzz','incompatible'))
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria.ia-evidence-diagnosis-probe-v1',cases=cases,checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL',
                factual_quality_status='NOT_EVALUATED',human_evaluation_status='NOT_PERFORMED',
                general_learning_status='NOT_ESTABLISHED',
                limitation='Read-only operator guidance tested over known finite-map fixtures; no independent human usefulness evaluation. Diagnostic inputs exclude evaluator reference answers. Candidates and learning are unchanged.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args = parser.parse_args(); report = probe(args.library)
    report['report_content_sha256'] = fingerprint(report)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,ensure_ascii=False,sort_keys=True,separators=(',',':'))+'\n')
    print(json.dumps(dict(integrity_status=report['integrity_status'],cases=len(report['cases']),
                         checks=sum(report['checks'].values()),total=len(report['checks']),sha=report['report_content_sha256'])))
    raise SystemExit(0 if report['integrity_status']=='PASS' else 1)


if __name__=='__main__': main()
