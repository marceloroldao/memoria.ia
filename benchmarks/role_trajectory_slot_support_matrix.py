from __future__ import annotations

import json

from memoria_resolutiva.trajectory_policy_gate_experimental import ExperimentalTrajectoryPolicyGate


def make_domain(length: int):
    roles = [f"r{i}" for i in range(length)]
    a = [f"a{i}" for i in range(length)]
    b = [f"b{i}" for i in range(length)]
    c = [f"c{i}" for i in range(length)]
    anchors = {roles[i]: [a[i], b[i], c[i]] for i in range(length)}
    return roles, a, b, c, anchors


def build(length: int, base_repeat: int, drift_repeat: int, pos: int):
    roles, a, b, c, anchors = make_domain(length)
    alt = list(a); alt[pos] = b[pos]
    gate = ExperimentalTrajectoryPolicyGate(use_native=False)
    gate.observe([" ".join(a), " ".join(b), " ".join(c)] * base_repeat + [" ".join(alt)] * drift_repeat)
    for role in roles:
        gate.register_role(role, anchors[role])
    gate.register_pattern(tuple(roles))
    return gate, a, alt


def support(gate, left: str, offset: int, right: str) -> float:
    p = gate.router.roles.memory.associator.profiles.get(left)
    if not p: return 0.0
    wanted = p.get((offset, right), 0)
    total = sum(n for (o, _), n in p.items() if o == offset)
    return wanted / total if total else 0.0


def delta_for(gate, base, alt, pos):
    if pos == 0:
        left, offset, old, new = base[1], -1, base[0], alt[0]
    else:
        left, offset, old, new = base[pos-1], 1, base[pos], alt[pos]
    return support(gate,left,offset,old)-support(gate,left,offset,new)


def state(delta, deadband):
    return "stable" if delta > deadband else "regime_shift" if delta < -deadband else "uncertain"


def case(length, base_repeat, pos):
    clean, base, alt = build(length, base_repeat, 0, pos)
    if not clean.calibrate(): return {"length":length,"base":base_repeat,"pos":pos,"calibrated":False}
    deadband = clean._margin / 2
    rows=[]
    for d in sorted(set([0,max(1,base_repeat//4),max(1,base_repeat//2),base_repeat,base_repeat*2,base_repeat*4])):
        gate, base, alt = build(length,base_repeat,d,pos)
        x=delta_for(gate,base,alt,pos)
        rows.append({"drift":d,"ratio":d/base_repeat,"delta":x,"state":state(x,deadband)})
    rank={"stable":0,"uncertain":1,"regime_shift":2}
    monotonic=all(rank[rows[i]["state"]] <= rank[rows[i+1]["state"]] for i in range(len(rows)-1))
    equal=next(r for r in rows if r["ratio"]==1.0)
    return {"length":length,"base":base_repeat,"pos":pos,"calibrated":True,"deadband":deadband,"rows":rows,"monotonic":monotonic,"equal_uncertain":equal["state"]=="uncertain","strong_shift":rows[-1]["state"]=="regime_shift"}


def main():
    out=[]
    for length in (4,5,6):
        for base in (2,4,8,16):
            for pos in (0,length//2,length-1):
                out.append(case(length,base,pos))
    passed=all(r.get("calibrated") and r.get("monotonic") and r.get("equal_uncertain") and r.get("strong_shift") for r in out)
    print(json.dumps({"experiment":"slot support scale matrix","cases":out,"summary":{"total":len(out),"passed":sum(1 for r in out if r.get("calibrated") and r.get("monotonic") and r.get("equal_uncertain") and r.get("strong_shift")),"all_passed":passed}},ensure_ascii=False,indent=2))
    if not passed: raise SystemExit(1)

if __name__ == "__main__": main()
