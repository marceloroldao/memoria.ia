"""Operator guidance from observed evidence only; no reference answers or writes."""
from trajectory_analogy_frame_probe import middle, occurrences
from trajectory_transform_trace_core import trace_transform


def diagnose_evidence(reading, observations, query):
    raw = reading['raw_view']
    trace = trace_transform({'result':reading},observations,query)
    if not trace['candidate_set_equal']:
        raise RuntimeError('diagnostic trace disagrees with actual transform route')
    symbols = tuple(map(ord,query)); roots = sorted({r['text'] for r in observations if r['source_kind']=='user_turn'})
    frames = []; transform = {f['frame_id']:f for f in trace['frames']}
    for frame in raw['frames']:
        if frame['route']=='symbol_transform':
            frames.append(transform[frame['frame_id']]); continue
        if frame['route']!='literal_copy':
            raise ValueError('unknown diagnostic route')
        item = dict(frame_id=frame['frame_id'],witnesses=frame['witnesses'])
        starts = occurrences(tuple(frame['source_prefix']),symbols)
        item['source_prefix_occurrences'] = len(starts)
        if len(starts)!=1:
            item['status']='SOURCE_PREFIX_COUNT'
        else:
            variable = middle(symbols[starts[0]:],tuple(frame['source_prefix']),tuple(frame['source_suffix']))
            if variable is None:
                item['status']='SOURCE_BOUNDARY'
            else:
                head = tuple(frame['target_prefix'])+variable+tuple(frame['target_bridge'])
                ending = tuple(frame['target_suffix'])
                item.update(variable=''.join(map(chr,variable)),target_head=''.join(map(chr,head)),
                            target_suffix=''.join(map(chr,ending)),target_checks=[])
                for text in roots:
                    payload = tuple(map(ord,text))
                    status = ('TARGET_PREFIX_MISMATCH' if payload[:len(head)]!=head else
                              'TARGET_SUFFIX_MISMATCH' if payload[-len(ending):]!=ending else
                              'EMPTY_VALUE_SLOT' if middle(payload,head,ending) is None else 'MATCH')
                    item['target_checks'].append(dict(text=text,status=status))
                item['status']='ADMITTED_OBSERVED_ROOTS' if any(r['status']=='MATCH' for r in item['target_checks']) else 'NO_OBSERVED_TARGET_MATCH'
        frames.append(item)
    literal_texts = sorted({t['text'] for f in frames if f['frame_id'].startswith('literal_copy:')
                            for t in f.get('target_checks',[]) if t['status']=='MATCH'})
    actual_literal = sorted(c['text'] for c in raw['candidates']
                            if any(e['route']=='literal_copy' for e in c['route_evidence']))
    if literal_texts != actual_literal:
        raise RuntimeError('diagnostic trace disagrees with actual copy route')
    findings = []
    def add(code,message,guidance,affected=()):
        findings.append(dict(code=code,message=message,guidance=guidance,
                             frame_ids=[f['frame_id'] for f in affected]))
    compatible = [f for f in frames if f['status'] not in ('SOURCE_PREFIX_COUNT','SOURCE_BOUNDARY')]
    missing = [f for f in frames if f['status']=='UNWITNESSED_QUERY_SYMBOLS']
    no_target = [f for f in frames if f['status']=='NO_OBSERVED_TARGET_MATCH']
    boundaries = [f for f in frames if any(t['status'] in ('TARGET_SUFFIX_MISMATCH','EMPTY_VALUE_SLOT') for t in f.get('target_checks',[]))]
    if not frames:
        add('NO_LEARNED_FRAMES','Não há molduras aprendidas neste escopo.',
            'Forneça exemplos observados de pergunta e conteúdo em sequência, mantendo suas origens.')
    elif not compatible:
        add('NO_COMPATIBLE_SOURCE_FRAME','Nenhuma moldura admite a escrita e os limites desta consulta.',
            'Confira a consulta e, se necessário, demonstre essa forma de perguntar com exemplos observados.',frames)
    if missing:
        add('UNWITNESSED_SYMBOLS_IN_FRAMES','Algumas rotas não têm mapa para todos os símbolos da variável.',
            'Inspecione os símbolos indicados e forneça exemplos reais do mapeamento necessário, inclusive pares identidade.',missing)
    if no_target:
        add('NO_OBSERVED_DESTINATION_IN_FRAMES','Algumas molduras aplicáveis não admitem nenhum destino observado.',
            'Confira o mapa, o conteúdo disponível e os limites da moldura; só acrescente conteúdo que tenha sido observado.',no_target)
    if boundaries:
        add('OBSERVED_TARGET_BOUNDARY_MISMATCH','Há conteúdo com prefixo compatível excluído pelo final ou pelo espaço de valor da moldura.',
            'Confira se esses conteúdos são pertinentes. Se forem, demonstre a variação com exemplos observados.',boundaries)
    candidates = raw['candidates']; available = reading['available_candidates']; withheld = reading['withheld_candidates']
    admitted_transforms = [f for f in trace['frames'] if f['status']=='ADMITTED_OBSERVED_ROOTS']
    if len({f['converted'] for f in admitted_transforms})>1:
        add('COMPETING_TRANSFORM_DESTINATIONS','Rotas de transformação admitidas produzem destinos diferentes.',
            'Inspecione as candidatas e os testemunhos; a leitura não estabelece qual alternativa é verdadeira.',admitted_transforms)
    if len(candidates)>1:
        add('MULTIPLE_OBSERVED_CANDIDATES','A leitura bruta contém mais de uma candidata observada.',
            'Confira a proveniência e o contexto de cada candidata; quantidade de rotas não é votação de verdade.')
    if withheld:
        add('EXPLICIT_FEEDBACK_WITHHOLDS_CANDIDATES','Há candidatas preservadas na leitura bruta e suspensas por feedback.',
            'Confira o histórico de feedback e suas retiradas antes de concluir que falta conteúdo na memória.')
    if candidates and not findings:
        add('OBSERVED_CANDIDATE_REQUIRES_REVIEW','Há uma candidata observada, com adequação factual ainda não avaliada.',
            'Confira se o conteúdo e a proveniência atendem à pergunta.')
    return dict(format='memoria.ia-evidence-diagnosis-v1',
                status='FEEDBACK_WITHHELD' if candidates and not available else 'CANDIDATES_REQUIRE_REVIEW' if candidates else 'UNRESOLVED',
                findings=findings,frames=frames,transform_trace=trace,
                raw_candidate_count=len(candidates),available_candidate_count=len(available),withheld_candidate_count=len(withheld),
                query_recorded=False,request_dispatched=False,learning_performed=False,
                answer=None,qualified=False,selected_target=None,selection_used=False,
                factual_quality_status='NOT_EVALUATED',general_learning_status='NOT_ESTABLISHED')
