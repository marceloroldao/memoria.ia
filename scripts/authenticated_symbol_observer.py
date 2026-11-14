#!/usr/bin/env python3
"""Experimental shared-key observer. Input secrets are never echoed or persisted.

A valid MAC authenticates possession of a configured shared key, not sensor truth.
The verifier also holds this key and can forge packets: no nonrepudiation claim.
"""
import hashlib
import hmac
import json
from pathlib import Path
import re
import sys

import controlled_symbol_observer as world

FORMAT = 'shared-key-symbol-observer-v1'
DOMAIN = b'memoria.ia/experimental-observer/hmac-sha256/v1\x00'


def versions():
    return dict(worker=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                world=hashlib.sha256(Path(world.__file__).read_bytes()).hexdigest())


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r'[a-zA-Z0-9_.:-]{1,96}', value):
        raise ValueError('invalid identifier')
    return value


def validate_task(task):
    if not isinstance(task, dict) or set(task) != {'format', 'region', 'forecast_id', 'query', 'source_id', 'key_id', 'challenge', 'request', 'versions'}:
        raise ValueError('invalid authenticated task schema')
    for name in ('region', 'forecast_id', 'source_id', 'key_id'):
        identifier(task[name])
    if task['format'] != FORMAT or not isinstance(task['challenge'], str) or not re.fullmatch('[0-9a-f]{64}', task['challenge']):
        raise ValueError('invalid task format or challenge')
    request = world.validate_request(task['request'])
    if task['query'] != 'Q[' + request['entity'] + ']?' or task['versions'] != versions():
        raise ValueError('task query or worker version mismatch')
    return json.loads(world.canonical(task))


def validate_key(key):
    if type(key) is not bytes or len(key) < 32:
        raise ValueError('shared key requires at least 32 bytes')
    return key


def mac(body, key):
    return hmac.new(validate_key(key), DOMAIN + world.canonical(body).encode('utf-8'), 'sha256').hexdigest()


def issue(task, key):
    task = validate_task(task)
    body = dict(task=task, packet=world.observe(task['request']))
    return dict(body=body, mac=mac(body, key))


def verify(envelope, task, key):
    task = validate_task(task)
    if (not isinstance(envelope, dict) or set(envelope) != {'body', 'mac'} or
            not isinstance(envelope['body'], dict) or set(envelope['body']) != {'task', 'packet'} or
            envelope['body']['task'] != task or not isinstance(envelope['mac'], str) or
            not re.fullmatch('[0-9a-f]{64}', envelope['mac'])):
        raise ValueError('authenticated envelope does not match frozen task')
    if not hmac.compare_digest(mac(envelope['body'], key), envelope['mac']):
        raise ValueError('shared-key authentication failed')
    return envelope['body']['packet']


def main():
    for line in sys.stdin:
        try:
            value = json.loads(line)
            if not isinstance(value, dict) or set(value) != {'task', 'key_hex'}:
                raise ValueError('invalid signing input')
            key = bytes.fromhex(value['key_hex'])
            result = dict(ok=True, envelope=issue(value['task'], key))
        except (ValueError, TypeError, KeyError):
            # Never echo input or exception text: it may contain secret material.
            result = dict(ok=False, error='authenticated observer rejected input')
        print(world.canonical(result), flush=True)


if __name__ == '__main__':
    main()
