#!/usr/bin/env python3
"""Independent toy measurement process; no model, forecast or memory input."""
import json
import re
import sys

LAWS = ('linear_up','linear_down','constant','hidden_break','accelerating')


def measure(request):
    if not isinstance(request,dict) or set(request)!={'seed','entity','tick','law'}:
        raise ValueError('invalid world request')
    seed,entity,tick,law = (request[k] for k in ('seed','entity','tick','law'))
    if (type(seed) is not int or not 0<=seed<=10**9 or not isinstance(entity,str) or
            not re.fullmatch('[a-z]{2}',entity) or type(tick) is not int or not 0<=tick<=1000 or law not in LAWS):
        raise ValueError('invalid world request')
    base = 100 + (seed + sum(ord(c) for c in entity)) % 89
    offset = {'linear_up':tick, 'linear_down':-2*tick, 'constant':0,
              'hidden_break':tick if tick<3 else tick+4, 'accelerating':tick*tick}[law]
    value = base + offset
    return dict(entity=entity,tick=tick,value=value,text=f'M[{entity};{tick}]={value}.')


def main():
    for line in sys.stdin:
        try:
            result=dict(ok=True,measurement=measure(json.loads(line)))
        except (ValueError,TypeError,KeyError):
            result=dict(ok=False,error='measurement request rejected')
        print(json.dumps(result,sort_keys=True),flush=True)


if __name__=='__main__':
    main()
