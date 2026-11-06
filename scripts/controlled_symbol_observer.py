#!/usr/bin/env python3
"""Standalone deterministic simulated observer: standard-library input/output only.

The input schema contains no hypothesis, candidate, memory path or forecast receipt.
Digests are checksums, not source authentication.
"""
import hashlib
import json
import re
import sys


FORMAT = 'controlled-symbol-observer-v1'


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode('utf-8')).hexdigest()


def validate_request(request):
    if not isinstance(request, dict) or set(request) != {'world_seed', 'entity', 'tick', 'sensor_mode'}:
        raise ValueError('observer requires only world_seed, entity, tick and sensor_mode')
    if type(request['world_seed']) is not int or not 0 <= request['world_seed'] <= 10**9:
        raise ValueError('invalid world seed')
    if not isinstance(request['entity'], str) or not re.fullmatch('[a-z]{2}', request['entity']):
        raise ValueError('entity must be exactly two lowercase symbols')
    if type(request['tick']) is not int or not 0 <= request['tick'] <= 1000:
        raise ValueError('invalid simulation tick')
    if request['sensor_mode'] not in ('faithful', 'lagged'):
        raise ValueError('unknown sensor mode')
    return dict(request)


def world_value(world_seed, entity, tick):
    return 100 + ((world_seed + sum((i + 1) * (ord(c) - 96) for i, c in enumerate(entity))) % 89) + tick


def render(entity, value):
    return f'R[{entity}]={value}.'


def observe(request):
    request = validate_request(request)
    observed_tick = request['tick'] if request['sensor_mode'] == 'faithful' else max(0, request['tick'] - 1)
    value = world_value(request['world_seed'], request['entity'], observed_tick)
    packet = dict(format=FORMAT, request=request, request_sha256=digest(request), reported_tick=observed_tick,
                  value=value, text=render(request['entity'], value))
    packet['result_sha256'] = digest(packet)
    return packet


def main():
    for line in sys.stdin:
        try:
            result = dict(ok=True, observation=observe(json.loads(line)))
        except (ValueError, TypeError, KeyError) as error:
            result = dict(ok=False, error=str(error))
        print(canonical(result), flush=True)


if __name__ == '__main__':
    main()
