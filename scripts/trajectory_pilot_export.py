"""Export an existing locked operator session without recording new events."""
import json
import os
from pathlib import Path
import tempfile

from trajectory_region_evidence_probe import fingerprint


def snapshot(session, scope):
    history = session.execute(dict(op='history', scope=scope))
    audit = session.execute(dict(op='review_outcomes', scope=scope))
    result = audit['result']
    completed = {row['event']['decision_id'] for row in result['outcomes']}
    report = dict(
        format='memoria.ia-operator-pilot-export-v1', scope=scope,
        history=history, review_audit=audit,
        decisions_without_outcomes=[row['event']['decision_id'] for row in result['decisions']
                                    if row['event']['decision_id'] not in completed],
        human_evaluation_status='NOT_VERIFIED', factual_quality_status='NOT_EVALUATED',
        general_learning_status='NOT_ESTABLISHED', causal_attribution='NOT_ESTABLISHED',
        coverage='Selected scope observations, feedback projection, withdrawals and review audit; not a storage backup',
    )
    report['sha256'] = fingerprint(report)
    return report


def export(session, scope, output):
    output = Path(output)
    # Resolve the parent, retaining the final name so even dangling symlinks are refused.
    output = output.parent.resolve() / output.name
    data_dir = Path(session.owner.name).resolve().parent
    if output == data_dir or data_dir in output.parents:
        raise ValueError('Escolha um arquivo fora da pasta de dados do piloto.')
    report = snapshot(session, scope)
    temporary = None
    try:
        # Publish a complete file with an exclusive hard link; never overwrite an existing path.
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=output.parent,
                                         prefix='.pilot-export-', delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(report, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink()
    return report
