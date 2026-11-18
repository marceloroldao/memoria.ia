#!/usr/bin/env python3
"""Read-only logical snapshot and portable HTML/JSON report for the forecast lab."""
import argparse
from html import escape
import json
from pathlib import Path
import sys

import trajectory_forecast_lab as forecast

FORMAT='memoria.ia-forecast-report-v1'
LABELS={
    'MATCHES_SELECTED_PROPOSAL':'Coincide com o registro',
    'DIFFERS_FROM_SELECTED_PROPOSAL':'Diverge do registro',
    'ABSTAINED_BEFORE_OBSERVATION':'Abstenção',
    'PENDING':'Pendente de vínculo',
    'DIVERGENT_LATER_MEASUREMENTS':'Medições conflitantes',
    'UNVERIFIABLE_HISTORY':'Histórico não verificável',
    'INCOMPLETE':'Previsão incompleta',
}
COUNT_KEYS={
    'MATCHES_SELECTED_PROPOSAL':'matches',
    'DIFFERS_FROM_SELECTED_PROPOSAL':'mismatches',
    'ABSTAINED_BEFORE_OBSERVATION':'abstentions',
    'PENDING':'pending',
    'DIVERGENT_LATER_MEASUREMENTS':'conflicts',
    'UNVERIFIABLE_HISTORY':'unverifiable',
    'INCOMPLETE':'incomplete',
}


def build_report(history,status,scope):
    """Pure projection; never infer a linkage from matching entity/tick alone."""
    observations=[]
    for row in history['entries']:
        point=forecast.base.parse(row['text'])
        if point is None: raise ValueError('invalid measurement in report')
        observations.append(dict(**point,source_id=row['source_id'],address=forecast.base.audit.address(row)))
    predictions=[]
    counts={key:0 for key in COUNT_KEYS.values()}
    for summary in history['predictions']:
        value=dict(summary)
        state='INCOMPLETE' if summary['state']=='INCOMPLETE' else summary['comparison']
        if state not in COUNT_KEYS: raise ValueError('unknown comparison status')
        counts[COUNT_KEYS[state]]+=1
        selector_id=forecast.ids(summary['prediction_id'])['selector']
        linked=[]
        for entry in history['journal']:
            event=entry['event']
            if event['op']!='OUTCOME' or event['forecast_id']!=selector_id: continue
            row=event['observation'];point=forecast.base.parse(row['text'])
            if point is None: raise ValueError('invalid linked measurement in report')
            linked.append(dict(**point,source_id=row['source_id'],address=forecast.base.audit.address(row)))
        proposal=value.get('proposal')
        difference=None
        if (value.get('history_verified') is True and proposal is not None and len(linked)==1 and
                state in ('MATCHES_SELECTED_PROPOSAL','DIFFERS_FROM_SELECTED_PROPOSAL')):
            difference=linked[0]['value']-proposal['value']
        value.update(report_status=state,linked_observations=linked,observed_minus_proposed=difference)
        predictions.append(value)
    payload=dict(format=FORMAT,scope=scope,observations=observations,predictions=predictions,journal=history['journal'],
                 counts=dict(observations=len(observations),predictions=len(predictions),**counts),
                 limits=status['limits'],repair_prediction_ids=status['repair_prediction_ids'],
                 repair_observation_ids=status['repair_observation_ids'],
                 answer=None,qualified=False,factual_quality_status='NOT_EVALUATED',
                 note='Static logical snapshot. Declared measurements and supplied arithmetic rules; no source truth or independent confirmation.')
    # Freeze ordinary JSON values before releasing the native owner.
    payload=json.loads(json.dumps(payload,ensure_ascii=False,sort_keys=True,allow_nan=False))
    payload['snapshot_id']=forecast.base.fingerprint(payload)
    return payload


def collect_report(lab,scope='csv'):
    with lab.lock:
        history=lab.execute(dict(op='history',scope=scope))['result']
        status=lab.execute(dict(op='status',scope=scope))['result']
        return build_report(history,status,scope)


def validate_report(report):
    if (not isinstance(report,dict) or report.get('format')!=FORMAT or report.get('qualified') is not False or
            report.get('answer') is not None or
            report.get('snapshot_id')!=forecast.base.fingerprint({k:v for k,v in report.items() if k!='snapshot_id'})):
        raise ValueError('report snapshot was changed or has invalid format')
    json.dumps(report,allow_nan=False)
    return report


def h(value):
    return escape(str(value),quote=True)


def numeric_point(point):
    if (not isinstance(point,dict) or type(point.get('tick')) is not int or type(point.get('value')) is not int or
            not 0<=point['tick']<=1000 or not -10000<=point['value']<=10000):
        raise ValueError('invalid report plot coordinates')
    forecast.base.request_fields(point['entity'],point['tick'])
    return point


def plot(report,entity):
    measured=[numeric_point(p) for p in report['observations'] if p['entity']==entity]
    proposed=[numeric_point(p['proposal']) for p in report['predictions'] if
              p['entity']==entity and p.get('history_verified') is True and p.get('proposal') is not None]
    points=measured+proposed
    if not points: return '<p class="muted">Sem pontos para esta entidade.</p>'
    xmin=min(p['tick'] for p in points);xmax=max(p['tick'] for p in points)
    ymin=min(p['value'] for p in points);ymax=max(p['value'] for p in points)
    if xmin==xmax: xmin-=1;xmax+=1
    if ymin==ymax: ymin-=1;ymax+=1
    def position(p):
        return 52+(p['tick']-xmin)/(xmax-xmin)*568,220-(p['value']-ymin)/(ymax-ymin)*190
    result=['<svg viewBox="0 0 640 264" role="img" aria-label="'+h(entity)+' — medições e hipóteses">',
            '<title>'+h(entity)+' — pontos declarados e hipóteses sem qualificação factual</title>',
            '<path class="axis" d="M52 24 V220 H620" fill="none"/>']
    for x,label in ((52,xmin),(620,xmax)):
        result.append('<text class="tick" x="'+str(x)+'" y="239" text-anchor="middle">'+h(label)+'</text>')
    for y,label in ((32,ymax),(220,ymin)):
        result.append('<text class="tick" x="45" y="'+str(y)+'" text-anchor="end">'+h(label)+'</text>')
    result.append('<text class="tick" x="336" y="259" text-anchor="middle">Tick declarado</text>')
    for point in measured:
        x,y=position(point)
        result.append('<circle class="measured" data-series="observed" data-tick="'+str(point['tick'])+
                      '" data-value="'+str(point['value'])+'" cx="'+f'{x:.2f}'+'" cy="'+f'{y:.2f}'+'" r="4.5"><title>'+
                      h('Medição '+entity+'; tick '+str(point['tick'])+': '+str(point['value']))+'</title></circle>')
    for point in proposed:
        x,y=position(point)
        shape=f'M{x:.2f} {y-6:.2f} L{x+6:.2f} {y:.2f} L{x:.2f} {y+6:.2f} L{x-6:.2f} {y:.2f} Z'
        result.append('<path class="proposed" data-series="proposal" data-tick="'+str(point['tick'])+
                      '" data-value="'+str(point['value'])+'" d="'+shape+'"><title>'+
                      h('Hipótese '+entity+'; tick '+str(point['tick'])+': '+str(point['value']))+'</title></path>')
    result.append('</svg>')
    return ''.join(result)


CSS="""
:root{color-scheme:dark;font-family:system-ui,-apple-system,sans-serif;color:#edf3ff;background:#08111f}
*{box-sizing:border-box}body{margin:0;padding:24px}main{max-width:1120px;margin:auto}
h1{font-size:clamp(1.5rem,4vw,2.3rem);margin:8px 0}h2{font-size:1.2rem;margin-top:0}
p{line-height:1.6}.muted{color:#b9c8de}.eyebrow{color:#5fddf5;letter-spacing:.14em;font-size:.8rem}
.card{background:#101e31;border:1px solid #2d405a;border-radius:14px;padding:20px;margin:18px 0;min-width:0}
.metrics{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.metric{background:#101e31;border:1px solid #2d405a;border-radius:12px;padding:16px;min-width:0}
.metric strong{display:block;font-size:1.8rem}.metric span{color:#b9c8de;font-size:.88rem}
.alert{border-left:4px solid #ffd17a}.bad{border-left:4px solid #ff9f9f}
.table-wrap{overflow-x:auto}table{width:100%;border-collapse:collapse;min-width:640px}
th,td{text-align:left;vertical-align:top;border-bottom:1px solid #2d405a;padding:12px 10px;font-size:.9rem}
th{color:#b9c8de}code,pre{font-family:ui-monospace,monospace;overflow-wrap:anywhere}
pre{white-space:pre-wrap;max-height:28rem;overflow:auto;font-size:.8rem;line-height:1.5}
summary{cursor:pointer;color:#5fddf5;padding:8px 0}summary:focus-visible{outline:2px solid #ffd17a}
.badge{display:inline-block;padding:4px 8px;border:1px solid #536780;border-radius:8px}
.mismatch,.unverifiable,.conflict{color:#ffb8b8}.pending,.incomplete{color:#ffd17a}
svg{display:block;width:100%;height:auto}.axis{stroke:#6c819e;stroke-width:1}
.tick{fill:#b9c8de;font-size:11px}.measured{fill:#5fddf5;stroke:#08111f;stroke-width:1}
.proposed{fill:none;stroke:#ffd17a;stroke-width:2}.legend{display:flex;flex-wrap:wrap;gap:20px;font-size:.85rem}
.legend .observation{color:#5fddf5}.legend .hypothesis{color:#ffd17a}
footer{padding:20px 0;font-size:.85rem;color:#b9c8de}small{line-height:1.5}
@media(max-width:600px){body{padding:12px}.card{padding:14px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
"""


def render_html(report,title='Relatório de previsões · Memoria.ia'):
    validate_report(report)
    counts=report['counts']
    metrics=[('Medições declaradas',counts['observations']),('Pedidos de previsão',counts['predictions']),
             ('Coincidências com registros',counts['matches']),('Divergências de registros',counts['mismatches']),
             ('Abstenções',counts['abstentions']),('Pendências',counts['pending']+counts['incomplete'])]
    result=['<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width,initial-scale=1">',
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; base-uri \'none\'; form-action \'none\'">',
            '<title>'+h(title)+'</title><style>'+CSS+'</style></head><body><main>',
            '<header><p class="eyebrow">MEMORIA.IA · CONSULTA LOCAL</p><h1>'+h(title)+'</h1>',
            '<p class="muted">Escopo '+h(report['scope'])+' · Retrato estático '+h(report['snapshot_id'][:16])+'</p>',
            '<p>As medições são declarações da fonte. As hipóteses não foram promovidas a fatos.</p></header>',
            '<section class="metrics" aria-label="Contagens do retrato">']
    for label,value in metrics:
        result.append('<div class="metric"><strong>'+h(value)+'</strong><span>'+h(label)+'</span></div>')
    result.append('</section>')
    if report['repair_prediction_ids'] or report['repair_observation_ids']:
        result.append('<section class="card alert"><h2>Retomada necessária</h2><p>Há operações incompletas. Este relatório não executou retomada.</p><pre>'+
                      h(json.dumps(dict(predictions=report['repair_prediction_ids'],observations=report['repair_observation_ids']),ensure_ascii=False,indent=2))+'</pre></section>')
    if counts['unverifiable']:
        result.append('<section class="card bad"><h2>Histórico não verificável</h2><p>Há hipóteses cujo histórico não pôde ser reproduzido. Seus valores continuam na tabela, mas não entram no gráfico de propostas verificáveis.</p></section>')
    if counts['conflicts']:
        result.append('<section class="card bad"><h2>Medições conflitantes</h2><p>Os valores vinculados foram preservados. Não foi escolhido um valor verdadeiro nem calculada uma média para resolver o conflito.</p></section>')
    entities=sorted({p['entity'] for p in report['observations']}|{p['entity'] for p in report['predictions']})
    result.append('<section class="card"><h2>Medições e hipóteses</h2><p class="legend"><span class="observation">● Medição declarada</span><span class="hypothesis">◇ Hipótese do seletor com histórico verificável</span></p>')
    if not entities: result.append('<p class="muted">Sem dados neste escopo.</p>')
    for entity in entities:
        result.append('<h3>'+h(entity)+'</h3>'+plot(report,entity))
    result.append('<p class="muted"><small>São pontos discretos, sem interpolação. Propostas das regras candidatas não escolhidas permanecem nos recibos.</small></p></section>')
    result.append('<section class="card"><h2>Confrontos registrados</h2><div class="table-wrap"><table><thead><tr><th>Alvo</th><th>Entidade</th><th>Hipótese</th><th>Medições vinculadas ao seletor</th><th>Observado − proposto</th><th>Estado</th></tr></thead><tbody>')
    for p in report['predictions']:
        state=p['report_status'];proposal=p.get('proposal')
        proposed='Não concluída' if state=='INCOMPLETE' else 'Abstenção' if proposal is None else str(proposal['value'])
        observed=', '.join(str(v['value']) for v in p['linked_observations']) or 'Sem vínculo'
        delta=p['observed_minus_proposed']
        delta='—' if delta is None else f'{delta:+d}'
        style={'DIFFERS_FROM_SELECTED_PROPOSAL':'mismatch','UNVERIFIABLE_HISTORY':'unverifiable','DIVERGENT_LATER_MEASUREMENTS':'conflict','PENDING':'pending','INCOMPLETE':'incomplete'}.get(state,'neutral')
        proof=dict(prediction_id=p['prediction_id'],forecast_receipt_id=p.get('forecast_receipt_id'),
                   selected_rule=p.get('selected_rule'),decision=p.get('decision'),scores=p.get('scores'),
                   linked_observations=p['linked_observations'],history_verified=p.get('history_verified'))
        result.append('<tr><td>'+h(p['target_tick'])+'</td><td>'+h(p['entity'])+'</td><td>'+h(proposed)+
                      '</td><td>'+h(observed)+'</td><td>'+h(delta)+'</td><td><span class="badge '+h(style)+'">'+h(LABELS[state])+
                      '</span><details><summary>Proveniência e regras</summary><pre>'+h(json.dumps(proof,ensure_ascii=False,sort_keys=True,indent=2))+'</pre></details></td></tr>')
    result.append('</tbody></table></div></section>')
    result.append('<section class="card"><h2>Observações preservadas</h2><div class="table-wrap"><table><thead><tr><th>Tick</th><th>Entidade</th><th>Valor</th><th>Origem</th><th>Endereço nativo</th></tr></thead><tbody>')
    for point in report['observations']:
        result.append('<tr><td>'+h(point['tick'])+'</td><td>'+h(point['entity'])+'</td><td>'+h(point['value'])+
                      '</td><td><code>'+h(point['source_id'])+'</code></td><td><code>'+h(json.dumps(point['address'],ensure_ascii=False))+'</code></td></tr>')
    result.append('</tbody></table></div></section>')
    result.append('<section class="card"><details><summary>Snapshot e journal completos em JSON</summary><pre>'+
                  h(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False))+'</pre></details></section>')
    result.append('<footer><p>Limites do piloto: '+h(report['limits']['observations_per_scope'])+' medições e '+
                  h(report['limits']['predictions_per_scope'])+' previsões por escopo. Qualidade factual não avaliada. Este arquivo não atualiza ao vivo.</p><p>Snapshot: <code>'+
                  h(report['snapshot_id'])+'</code></p></footer></main></body></html>')
    return ''.join(result)


def output_targets(data_dir,html_path,json_path=None):
    root=Path(data_dir).resolve()
    requested=[Path(html_path)]+([] if json_path is None else [Path(json_path)])
    if any(path.is_symlink() for path in requested): raise FileExistsError('report output must not be a symlink')
    paths=[path.resolve() for path in requested]
    if len(set(paths))!=len(paths): raise ValueError('HTML and JSON require distinct output paths')
    for i,path in enumerate(paths):
        if path==root or root in path.parents: raise ValueError('report output must be outside the data directory')
        if path.suffix.lower() not in (('.html','.htm') if i==0 else ('.json',)):
            raise ValueError('output extension must match HTML or JSON')
        if path.exists() or path.is_symlink(): raise FileExistsError('report output already exists: '+str(path))
    return paths


def write_report(report,data_dir,html_path,json_path=None,title='Relatório de previsões · Memoria.ia'):
    paths=output_targets(data_dir,html_path,json_path)
    page=render_html(report,title)
    bodies=[page]
    if json_path is not None: bodies.append(json.dumps(report,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n')
    # Preflight all targets, then exclusive creation. I/O failure may leave a
    # partial export; it never triggers an observation or prediction operation.
    for path,body in zip(paths,bodies):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('x',encoding='utf-8',newline='\n') as target: target.write(body)
    return dict(html=str(paths[0]),json=None if json_path is None else str(paths[1]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--scope',default='csv')
    parser.add_argument('--html',type=Path,required=True)
    parser.add_argument('--json',type=Path)
    parser.add_argument('--title',default='Relatório de previsões · Memoria.ia')
    args=parser.parse_args()
    try:
        native_dir=args.data_dir/'native'
        if not native_dir.is_dir() or not any(native_dir.iterdir()):
            raise ValueError('existing nonempty native data directory is required')
        output_targets(args.data_dir,args.html,args.json)
        with forecast.open_lab(args.library,args.data_dir) as lab: report=collect_report(lab,args.scope)
        paths=write_report(report,args.data_dir,args.html,args.json,args.title)
    except (ValueError,TypeError,KeyError,OSError) as error:
        print(json.dumps(dict(ok=False,error=str(error),qualified=False,native_mutations_requested=False),ensure_ascii=False))
        return 2
    print(json.dumps(dict(ok=True,format=FORMAT,snapshot_id=report['snapshot_id'],counts=report['counts'],
                          files=paths,answer=None,qualified=False,native_mutations_requested=False),ensure_ascii=False))
    return 0


if __name__=='__main__': raise SystemExit(main())
