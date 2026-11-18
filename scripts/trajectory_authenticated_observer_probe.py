#!/usr/bin/env python3
"""Opt-in shared-key admission for simulated observations; no truth promotion."""
import argparse
import copy
import json
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile

import authenticated_symbol_observer as signer
import controlled_symbol_observer as world
import trajectory_controlled_observer_probe as controlled
import trajectory_prediction_audit as audit
from mobile_region_replay import NativeProbe
from trajectory_feedback_transfer_stress import write_report
from trajectory_question_frame_probe import collect, persist
from trajectory_region_evidence_probe import fingerprint

WORKER = Path(signer.__file__)
# Public synthetic test fixture ONLY. Live callers must supply private random keys.
TEST_KEY = b'memoria-synthetic-fixture-key-0001'
SCENARIOS = ('faithful', 'lagged', 'unsigned_forgery', 'wrong_key', 'wrong_source',
             'wrong_challenge', 'revoked_key', 'authorized_false_report')


def freeze_task(native, region, query, forecast_id, actor_id, request, source_id, key_id, *, challenge=None):
    task = signer.validate_task(dict(format=signer.FORMAT, region=region, forecast_id=forecast_id,
        query=query, source_id=source_id, key_id=key_id,
        challenge=secrets.token_hex(32) if challenge is None else challenge,
        request=request, versions=signer.versions()))
    return audit.forecast(native, region, query, forecast_id, actor_id, observation_context=task)


def frozen_task(native, region, forecast_id):
    entries = [p for p in audit.journal(native, region) if p['event']['op'] == 'FORECAST'
               and p['event']['forecast_id'] == forecast_id]
    if len(entries) != 1:
        raise ValueError('forecast not found')
    binding = entries[0]['event']['receipt']
    task = signer.validate_task(binding.get('observation_context'))
    if (task['region'], task['forecast_id'], task['query']) != (region, forecast_id, binding['query']):
        raise ValueError('authenticated task scope mismatch')
    return task, binding


def run_observer(task, key):
    signer.validate_task(task); signer.validate_key(key)
    response = subprocess.run([sys.executable, str(WORKER)],
        input=world.canonical(dict(task=task, key_hex=key.hex())) + '\n',
        capture_output=True, text=True, timeout=10, check=True)
    result = json.loads(response.stdout)
    if result.get('ok') is not True:
        raise ValueError('authenticated observer rejected input')
    return result['envelope']


def trusted_key(task, keyring):
    key = keyring.get((task['source_id'], task['key_id']))
    if key is None:
        raise ValueError('source/key is not currently trusted')
    return signer.validate_key(key)


def ingest_result(native, region, forecast_id, outcome_id, envelope, keyring):
    audit.identity(outcome_id)
    task, binding = frozen_task(native, region, forecast_id)
    packet = signer.verify(envelope, task, trusted_key(task, keyring))
    controlled.validate_packet(packet)
    if packet['request'] != task['request']:
        raise ValueError('packet request differs from authenticated task')
    envelope = audit.metadata(envelope)
    rows, log = collect(native, [region]), audit.journal(native, region)
    observer_id = task['source_id']
    previous = [p['event'] for p in log if p['event']['op'] == 'OUTCOME' and p['event']['outcome_id'] == outcome_id]
    if previous:
        old = previous[0]
        if old['forecast_id'] != forecast_id or old.get('source_receipt') != envelope:
            raise ValueError('outcome identity reused with different authenticated receipt')
        return audit.observe_outcome(native, region, forecast_id, outcome_id, observer_id,
                                     audit.address(old['observation']), source_receipt=envelope)
    if not audit.verify_prefix(rows, binding):
        raise ValueError('frozen history unavailable')
    # Same packet identity as the unsigned bridge: new MAC/challenge cannot create time.
    source_id = 'controlled-observation:' + packet['result_sha256']
    existing = [r for r in rows if r['source_id'] == source_id]
    if existing:
        row = existing[0]
        if len(existing) != 1 or row['text'] != packet['text'] or row['source_kind'] != 'user_turn':
            raise ValueError('observation identity conflict')
        if row['sequence'] <= binding['cutoff_sequence']:
            raise ValueError('observation is not later than frozen cutoff')
        if any(p['event']['op'] == 'OUTCOME' and p['event']['forecast_id'] == forecast_id
               and audit.address(p['event']['observation']) == audit.address(row) for p in log):
            raise ValueError('observation already linked to this forecast')
    else:
        row = dict(hierarchy_id=region, source_id=source_id,
                   sequence=max((r['sequence'] for r in rows), default=-1) + 1,
                   text=packet['text'], source_kind='user_turn')
        persist(native, [row])
    return audit.observe_outcome(native, region, forecast_id, outcome_id, observer_id,
                                 audit.address(row), source_receipt=envelope)


def observe_task(native, region, forecast_id, outcome_id, keyring):
    task, _ = frozen_task(native, region, forecast_id)
    envelope = run_observer(task, trusted_key(task, keyring))
    return dict(envelope=envelope, link=ingest_result(native, region, forecast_id, outcome_id, envelope, keyring))


def authenticate_history(native, region, forecast_id, keyring):
    """Recheck current trust explicitly. Ordinary reconciliation never authenticates."""
    task, _ = frozen_task(native, region, forecast_id)
    key = trusted_key(task, keyring)
    outcomes = [p['event'] for p in audit.journal(native, region) if p['event']['op'] == 'OUTCOME'
                and p['event']['forecast_id'] == forecast_id]
    for outcome in outcomes:
        packet = signer.verify(outcome.get('source_receipt'), task, key)
        controlled.validate_packet(packet)
        row = outcome['observation']
        if (packet['request'] != task['request'] or outcome['observer_id'] != task['source_id'] or
                row['text'] != packet['text'] or row['source_id'] != 'controlled-observation:' + packet['result_sha256']):
            raise ValueError('authenticated journal binding mismatch')
    return dict(scope='CONFIGURED_SHARED_KEY_POSSESSION', authenticated_outcomes=len(outcomes),
                truth_established=False, nonrepudiation=False)


def scenario(library, seed, name):
    rows, region, query, entity, past = controlled.prepare_rows(seed)
    request = dict(world_seed=seed, entity=entity, tick=1,
                   sensor_mode='lagged' if name == 'lagged' else 'faithful')
    keyring = {('sensor-a', 'key-1'): TEST_KEY}
    with tempfile.TemporaryDirectory(prefix='memoria-auth-observer-') as directory:
        native = NativeProbe(library, Path(directory))
        try:
            persist(native, rows)
            frozen = freeze_task(native, region, query, 'f1', 'forecaster', request, 'sensor-a', 'key-1',
                                 challenge=world.digest([seed, name]))
            task = frozen['event']['receipt']['observation_context']
            issued = run_observer(task, TEST_KEY)
            envelope = copy.deepcopy(issued)
            if name in ('unsigned_forgery', 'authorized_false_report'):
                packet = envelope['body']['packet']
                packet.update(value=past['value'], text=world.render(entity, past['value']))
                packet['result_sha256'] = world.digest({k:v for k,v in packet.items() if k != 'result_sha256'})
                if name == 'authorized_false_report':
                    envelope['mac'] = signer.mac(envelope['body'], TEST_KEY)
            elif name == 'wrong_key':
                envelope = run_observer(task, b'wrong-synthetic-key-0000000000000')
            elif name in ('wrong_source', 'wrong_challenge'):
                other = dict(task, **({'source_id': 'sensor-b'} if name == 'wrong_source' else {'challenge': 'f'*64}))
                envelope = run_observer(other, TEST_KEY)
            elif name == 'revoked_key':
                keyring = {}
            before_rows, before_log = collect(native, [region]), audit.journal(native, region)
            rejection = None
            try:
                ingest_result(native, region, 'f1', 'o1', envelope, keyring)
            except ValueError as error:
                if name not in ('unsigned_forgery', 'wrong_key', 'wrong_source', 'wrong_challenge', 'revoked_key'):
                    raise
                rejection = str(error)
            after = audit.reconcile(native, region, 'f1')
            saved_rows, saved_log = collect(native, [region]), audit.journal(native, region)
            checks = dict(expected_admission=(rejection is None) == (name in ('faithful', 'lagged', 'authorized_false_report')),
                          forecast_immutable=saved_log[0] == before_log[0],
                          old_prefix_preserved=saved_rows[:len(before_rows)] == before_rows,
                          no_factual_promotion=after['answer'] is None and not after['qualified'] and not after['learning_applied'],
                          generic_audit_does_not_claim_auth=after['provenance_independence'] == 'NOT_ESTABLISHED',
                          no_key_persisted=TEST_KEY.hex() not in world.canonical(saved_log) and TEST_KEY.decode() not in world.canonical(saved_log))
            auth = None
            if rejection:
                checks['rejected_before_any_write'] = saved_rows == before_rows and saved_log == before_log
            else:
                auth = authenticate_history(native, region, 'f1', keyring)
                checks['authenticated_count'] = auth['authenticated_outcomes'] == 1
                replay = ingest_result(native, region, 'f1', 'o1', envelope, keyring)
                checks['exact_replay_no_write'] = replay['status'] == 'EXACT_REPLAY' and collect(native, [region]) == saved_rows and audit.journal(native, region) == saved_log
            native.reopen()
            checks['cold_comparison_equal'] = audit.reconcile(native, region, 'f1') == after
            if not rejection:
                checks['cold_authentication_equal'] = authenticate_history(native, region, 'f1', keyring) == auth
            return dict(scenario=name, rows=rows, request=request, frozen=frozen, issued_envelope=issued,
                        received_envelope=envelope, rejection=rejection, result=after, authentication=auth, checks=checks,
                        evaluator=dict(linked_reports_agree_with_world=[p['outcome']['event']['source_receipt']['body']['packet']['value'] == world.world_value(seed, entity, 1) for p in after['comparisons']], truth_used_for_learning=False))
        finally:
            native.close()


def probe(library, seed):
    cases = [scenario(library, seed, name) for name in SCENARIOS]
    checks = {f'{i}:{k}':v for i,c in enumerate(cases) for k,v in c['checks'].items()}
    return dict(format='memoria-authenticated-observer-probe-v1', seed=seed, cases=cases, checks=checks,
                integrity_status='PASS' if all(checks.values()) else 'FAIL', integrity_passed=sum(checks.values()), integrity_total=len(checks),
                limitation='Synthetic shared-key fixture, not deployed identity, PKI, nonrepudiation or truth. A key holder, including verifier, can forge. Authenticated lagged/false readings remain unqualified.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=20270121)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = probe(args.library, args.seed)
    result['report_content_sha256'] = fingerprint(result)
    write_report(args.output, result)
    print(json.dumps({k:result[k] for k in ('seed', 'integrity_status', 'integrity_passed', 'integrity_total', 'report_content_sha256')}))
    raise SystemExit(0 if result['integrity_status'] == 'PASS' else 1)


if __name__ == '__main__':
    main()
