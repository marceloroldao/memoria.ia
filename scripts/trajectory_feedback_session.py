#!/usr/bin/env python3
"""Single-writer local JSON-lines feedback laboratory; no answer qualification."""
import argparse
import fcntl
import json
from pathlib import Path
import re
import sys

from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import canonical, events, receipt, record
from trajectory_feedback_withdrawal_probe import feedback_projection, withdraw, withdrawal_read, withdrawals
from trajectory_question_frame_probe import collect
from trajectory_region_evidence_probe import fingerprint
from trajectory_evidence_diagnosis import diagnose_evidence
from trajectory_demonstration_review import review_demonstrations, validate_offers
from trajectory_review_decisions import open_review, record_decision, history as review_decision_history


class FeedbackSession:
    """Own one directory for the full session, serialize commands, flush writes."""
    def __init__(self, library, data_dir):
        self.native = None
        data_dir = Path(data_dir)
        data_dir.mkdir(parents=True, exist_ok=True)
        self.owner = (data_dir / 'feedback-session.lock').open('a')
        try:
            fcntl.flock(self.owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
            native_dir = data_dir / 'native'
            native_dir.mkdir(exist_ok=True)
            self.native = NativeProbe(Path(library), native_dir)
        except BaseException:
            self.owner.close()
            raise

    def close(self):
        if self.native is not None:
            self.native.close()
            self.native = None
        self.owner.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def flush(self):
        if self.native.lib.memoria_mobile_flush(self.native.handle) != 0:
            raise RuntimeError('native flush failed; persistence not confirmed')

    def execute(self, command):
        if not isinstance(command, dict):
            raise ValueError('command must be an object')
        scope = command.get('scope', 'principal')
        if not isinstance(scope, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', scope):
            raise ValueError('invalid scope')
        region = 'conversation:feedback-session:' + scope
        op = command.get('op')
        allowed = {
            'observe': {'event_id', 'text', 'source_kind'},
            'query': {'text'},
            'diagnose': {'text'},
            'review_examples': {'text', 'offers'},
            'open_review': {'text', 'offers'},
            'record_review_decision': {'receipt_id', 'decision_id', 'actor_id', 'choice', 'offer_id', 'reason'},
            'review_decisions': set(),
            'feedback': {'receipt', 'event_id', 'actor_id', 'stance'},
            'withdraw': {'request_id', 'actor_id', 'target'},
            'history': set(),
        }
        if op not in allowed or set(command) - (allowed[op] | {'op', 'scope'}):
            raise ValueError('unsupported command or fields')
        rows = collect(self.native, [region])
        # Historical replay is deliberately expensive; never analyze a partial window.
        if len(rows) > 64 or sum(len(r['text']) for r in rows) > 4096:
            raise ValueError('experimental session exceeds 64 rows or 4096 characters')
        if op == 'observe':
            text = command.get('text'); event_id = command.get('event_id')
            kind = command.get('source_kind', 'user_turn')
            if not isinstance(text, str) or not text.strip():
                raise ValueError('nonempty text required')
            if not isinstance(event_id, str) or not event_id or kind not in ('user_turn', 'assistant_generated'):
                raise ValueError('invalid observation identity or kind')
            source = 'session-observation:' + fingerprint(event_id)
            previous = [r for r in rows if r['source_id'] == source]
            if previous:
                if len(previous) != 1 or previous[0]['text'] != text or previous[0]['source_kind'] != kind:
                    raise ValueError('observation identity reused with different content')
                result = dict(status='EXACT_REPLAY', entry=previous[0])
            else:
                if len(rows) >= 64 or sum(len(r['text']) for r in rows) + len(text) > 4096:
                    raise ValueError('experimental observation limit reached')
                row = dict(hierarchy_id=region, source_id=source,
                           sequence=1+max((r['sequence'] for r in rows), default=0),
                           text=text, source_kind=kind)
                status, response = self.native.call('observe_structural_text', row)
                if status != 0 or response.get('duplicate'):
                    raise RuntimeError('observation rejected')
                result = dict(status='APPENDED', entry=row)
        elif op in ('query', 'diagnose', 'review_examples', 'open_review'):
            text = command.get('text')
            if not isinstance(text, str) or not text.strip() or len(text) > 4000:
                raise ValueError('invalid query')
            if op in ('review_examples', 'open_review'):
                validate_offers(command.get('offers'))
            result = withdrawal_read(self.native, region, text, enabled=True)
            result['receipts'] = [receipt(self.native, region, text, c['payload_id'])
                                  for c in result['raw_view']['candidates']]
            result['query_recorded'] = False
            if op in ('diagnose', 'review_examples', 'open_review'):
                result['diagnosis'] = diagnose_evidence(result, rows, text)
            if op in ('review_examples', 'open_review'):
                result['example_review'] = review_demonstrations(result, command['offers'])
            if op == 'open_review':
                result = open_review(self.native, region, text, fingerprint(rows), result)
                result.update(review_receipt_recorded=True, audit_contains_offered_texts=True,
                              examples_incorporated_into_learning=False, learning_performed=False)
        elif op == 'record_review_decision':
            def current_review(query, offers):
                reviewed = self.execute(dict(op='review_examples', scope=scope, text=query, offers=offers))['result']
                return reviewed, fingerprint(collect(self.native, [region]))
            result = record_decision(self.native, region, command.get('receipt_id'), command.get('decision_id'),
                                     command.get('actor_id'), command.get('choice'), command.get('offer_id'),
                                     command.get('reason'), current_review)
            result.update(operator_choice_recorded=True, examples_incorporated_into_learning=False,
                          learning_performed=False)
        elif op == 'review_decisions':
            result = review_decision_history(self.native, region)
        elif op == 'feedback':
            binding = command.get('receipt')
            if not isinstance(binding, dict) or binding.get('region') != region:
                raise ValueError('receipt is outside this scope')
            result = record(self.native, binding, command.get('event_id'),
                            command.get('actor_id'), command.get('stance'))
        elif op == 'withdraw':
            target = command.get('target')
            if not isinstance(target, dict):
                raise ValueError('exact feedback target required')
            result = withdraw(self.native, region, command.get('request_id'), command.get('actor_id'), target)
        else:
            ledger = events(self.native, region)
            controls = withdrawals(self.native, region)
            result = dict(entries=rows, feedback_projection=feedback_projection(ledger, controls),
                          withdrawal_history=controls)
        if op in ('observe', 'feedback', 'withdraw', 'open_review', 'record_review_decision'):
            self.flush()
            result['persisted'] = True
        return dict(format='memoria.ia-feedback-session-v1', scope=scope, operation=op,
                    result=json.loads(canonical(result)), answer=None, qualified=False,
                    selection_used=False, factual_quality_status='NOT_EVALUATED',
                    general_learning_status='NOT_ESTABLISHED')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    args = parser.parse_args()
    with FeedbackSession(args.library, args.data_dir) as session:
        for line in sys.stdin:
            try:
                result = session.execute(json.loads(line))
            except (ValueError, KeyError, TypeError) as error:
                result = dict(status='REJECTED', error=str(error))
            # Native/storage errors end the process; no misleading successful continuation.
            print(canonical(result), flush=True)


if __name__ == '__main__':
    main()
