#!/usr/bin/env python3
"""Local JSON-lines laboratory for observations and addressed feedback.

One owning process per directory; no network service or factual qualification.
"""
import argparse
from contextlib import contextmanager
import fcntl
import json
from pathlib import Path
import re
import sys
import threading

from mobile_region_replay import NativeProbe
from trajectory_feedback_ledger_probe import canonical, events, receipt, record
from trajectory_feedback_withdrawal_probe import (
    feedback_projection, withdraw, withdrawal_read, withdrawals,
)
from trajectory_question_frame_probe import collect, persist


def text(value, name, limit=4096):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{name} must be a nonempty string of at most {limit} characters')
    return value


class FeedbackLab:
    """All public operations share the withdrawal-aware policy and process lock."""
    def __init__(self, native, *, enable_feedback=False):
        self.native = native
        self.enable_feedback = enable_feedback
        self.lock = threading.RLock()

    def flush(self):
        if self.native.lib.memoria_mobile_flush(self.native.handle) != 0:
            raise RuntimeError('flush failed; write outcome uncertain, reopen before retry')

    def execute(self, request):
        if not isinstance(request, dict):
            raise ValueError('command must be a JSON object')
        op = request.get('op')
        fields = {
            'observe': {'source_id', 'text', 'source_kind'},
            'query': {'text'}, 'history': set(),
            'feedback': {'receipt', 'event_id', 'actor_id', 'stance'},
            'withdraw': {'event_id', 'request_id', 'actor_id'},
        }
        if not isinstance(op, str) or op not in fields:
            raise ValueError('unknown operation')
        if set(request) - (fields[op] | {'op', 'scope'}):
            raise ValueError('unknown command fields')
        scope = request.get('scope', 'principal')
        if not isinstance(scope, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', scope):
            raise ValueError('invalid scope')
        region = 'conversation:feedback-lab:' + scope
        with self.lock:
            # The composed reader is combinatorial. Refuse a whole operation
            # rather than silently evaluating a truncated learning window.
            rows = collect(self.native, [region])
            ledger = events(self.native, region)
            controls = withdrawals(self.native, region)
            if len(rows) > 64 or sum(len(r['text']) for r in rows) > 4096:
                raise ValueError('learning window exceeds laboratory limit')
            if len(ledger) > 64 or len(controls) > 64:
                raise ValueError('feedback history exceeds laboratory limit')
            if op == 'observe':
                source = text(request.get('source_id'), 'source_id', 128)
                body = text(request.get('text'), 'text')
                kind = request.get('source_kind', 'user_turn')
                if kind not in ('user_turn', 'assistant_generated'):
                    raise ValueError('invalid source_kind')
                old = [r for r in rows if r['source_id'] == source]
                if old:
                    if len(old) != 1 or old[0]['text'] != body or old[0]['source_kind'] != kind:
                        raise ValueError('source_id reused with different content')
                    result = dict(status='EXACT_REPLAY', entry=old[0])
                else:
                    if len(rows) >= 64 or sum(len(r['text']) for r in rows) + len(body) > 4096:
                        raise ValueError('observation exceeds laboratory limit')
                    row = dict(hierarchy_id=region, source_id=source,
                               sequence=1 + max((r['sequence'] for r in rows), default=0),
                               text=body, source_kind=kind)
                    persist(self.native, [row])
                    result = dict(status='APPENDED', entry=row)
                self.flush()
            elif op == 'query':
                query = text(request.get('text'), 'text')
                view = withdrawal_read(self.native, region, query, enabled=self.enable_feedback)
                bindings = [receipt(self.native, region, query, c['payload_id'])
                            for c in view['raw_view']['candidates']]
                result = dict(view=view, receipts=bindings, query_recorded=False)
            elif op == 'history':
                result = dict(entries=rows, feedback=feedback_projection(ledger, controls),
                              withdrawals=controls)
            else:
                if not self.enable_feedback:
                    raise ValueError('feedback policy disabled; start with --enable-feedback')
                event_id = text(request.get('event_id'), 'event_id', 128)
                actor = text(request.get('actor_id'), 'actor_id', 128)
                if op == 'feedback':
                    binding = request.get('receipt')
                    if not isinstance(binding, dict) or binding.get('region') != region:
                        raise ValueError('receipt scope mismatch')
                    # Validate JSON values before any native write.
                    canonical(binding)
                    if len(ledger) >= 64 and not any(e['event']['event_id'] == event_id for e in ledger):
                        raise ValueError('feedback event limit reached')
                    result = record(self.native, binding, event_id, actor, request.get('stance'))
                else:
                    request_id = text(request.get('request_id'), 'request_id', 128)
                    targets = [e for e in ledger if e['event']['event_id'] == event_id]
                    if len(targets) != 1:
                        raise ValueError('feedback event not found in scope')
                    if len(controls) >= 64 and not any(c['event']['request_id'] == request_id for c in controls):
                        raise ValueError('withdrawal event limit reached')
                    result = withdraw(self.native, region, request_id, actor, targets[0])
                self.flush()
            return dict(format='memoria.ia-feedback-lab-v1', op=op, scope=scope,
                        feedback_enabled=self.enable_feedback, result=result,
                        answer=None, qualified=False, selection_used=False,
                        factual_quality_status='NOT_EVALUATED')


@contextmanager
def open_lab(library, data_dir, *, enable_feedback=False):
    """Advisory lock protects cooperating laboratory processes, not other tools."""
    data_dir.mkdir(parents=True, exist_ok=True)
    with (data_dir / 'feedback-lab.lock').open('a') as owner:
        fcntl.flock(owner, fcntl.LOCK_EX | fcntl.LOCK_NB)
        native_dir = data_dir / 'native'
        native_dir.mkdir(exist_ok=True)
        native = NativeProbe(library, native_dir)
        lab = FeedbackLab(native, enable_feedback=enable_feedback)
        try:
            yield lab
        finally:
            try:
                lab.flush()
            finally:
                native.close()


def serve(lab, input_stream, output_stream):
    """One response per command. Storage failures terminate instead of claiming rejection."""
    for line in input_stream:
        try:
            response = dict(ok=True, **lab.execute(json.loads(line)))
        except (ValueError, TypeError, KeyError) as error:
            response = dict(ok=False, error=str(error), answer=None, qualified=False,
                            selection_used=False)
        output_stream.write(json.dumps(response, ensure_ascii=False) + '\n')
        output_stream.flush()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--enable-feedback', action='store_true')
    args = parser.parse_args()
    with open_lab(args.library, args.data_dir, enable_feedback=args.enable_feedback) as lab:
        serve(lab, sys.stdin, sys.stdout)


if __name__ == '__main__':
    main()
