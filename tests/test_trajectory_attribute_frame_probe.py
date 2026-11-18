import copy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import trajectory_attribute_frame_probe as probe

REGION='conversation:test-attribute'


def rows(pairs=None,facts=('Meu gato se chama Alt.','Meu gato dorme no sofá.')):
    if pairs is None:
        pairs=[(d['question'],d['content']) for d in probe.demonstrations()
               if d['scope']=='pets' and d['question'].startswith('Qual nome')]
    result=[]
    def add(text,kind='user_turn'):
        result.append(dict(hierarchy_id=REGION,source_id='s'+str(len(result)),
            sequence=len(result)+1,text=text,source_kind=kind))
    for question,content in pairs:
        add(question);add(content);add('pausa','assistant_generated')
    for fact in facts: add(fact)
    return result


def texts(view):
    return {c['text'] for c in view['candidates']}


def test_new_entity_selects_observed_attribute_without_storing_question():
    data=rows();before=copy.deepcopy(data);reader=probe.AttributeFrameReader(data,REGION)
    view=reader.read('Qual nome do meu gato?')
    assert texts(view)=={'Meu gato se chama Alt.'}
    assert 'Qual nome do meu gato?' not in {r['text'] for r in data}
    assert view['proposal_payload_id'] is not None and view['answer'] is None
    assert view['qualified'] is False and view['absence_proven'] is False
    assert data==before and reader.read('Qual nome do meu gato?')==view


@pytest.mark.parametrize('question',[
    'Qual a cor do meu gato?','Qual nome do meu pássaro?',
    'Como se chama meu gato?','QUAL NOME DO MEU GATO?',
    'Qual nome do meu gato? Qual nome do meu cachorro?',
    'Lembre: Qual nome do meu gato?',
])
def test_unsupported_wording_or_entity_has_no_factual_absence_claim(question):
    view=probe.AttributeFrameReader(rows(),REGION).read(question)
    assert view['candidates']==[] and view['proposal_payload_id'] is None
    assert view['absence_proven'] is False and view['qualified'] is False


def test_two_attributes_are_discriminated_by_examples():
    pairs=[(d['question'],d['content']) for d in probe.demonstrations() if d['scope']=='pets']
    reader=probe.AttributeFrameReader(rows(pairs),REGION)
    assert texts(reader.read('Qual nome do meu gato?'))=={'Meu gato se chama Alt.'}
    assert texts(reader.read('Onde meu gato dorme?'))=={'Meu gato dorme no sofá.'}


def test_no_teaching_and_single_repeated_example_do_not_supply_distinct_witnesses():
    assert probe.AttributeFrameReader(rows([]),REGION).read('Qual nome do meu gato?')['candidates']==[]
    repeated=[('Qual nome do meu barco?','Meu barco se chama Vela.')]*8
    reader=probe.AttributeFrameReader(rows(repeated),REGION)
    assert reader.frames==() and reader.read('Qual nome do meu gato?')['candidates']==[]


def test_generated_target_breaks_the_third_training_pair():
    data=rows();data[7]['source_kind']='assistant_generated'
    assert probe.AttributeFrameReader(data,REGION).read('Qual nome do meu gato?')['candidates']==[]


def test_foreign_teaching_and_candidates_cannot_supply_local_roots():
    data=rows();foreign=[dict(r,hierarchy_id='conversation:foreign') for r in data]
    assert probe.AttributeFrameReader(foreign+data[9:],REGION).read('Qual nome do meu gato?')['candidates']==[]
    assert probe.AttributeFrameReader(data[:9]+foreign,REGION).read('Qual nome do meu gato?')['candidates']==[]


def test_conflicts_and_duplicate_origins_do_not_choose_a_majority():
    data=rows(facts=('Meu gato se chama Alt.','Meu gato se chama Bia.')+('Meu gato se chama Alt.',)*20)
    view=probe.AttributeFrameReader(data,REGION).read('Qual nome do meu gato?')
    assert texts(view)=={'Meu gato se chama Alt.','Meu gato se chama Bia.'}
    assert view['proposal_payload_id'] is None and view['reason']=='COMPETING_FRAME_CANDIDATES'
    assert len(next(c for c in view['candidates'] if 'Alt.' in c['text'])['origins'])==21


def test_misleading_teaching_can_route_to_the_wrong_attribute_without_qualification():
    pairs=[('Qual nome do meu '+s+'?','Meu '+s+' é '+v+'.')
           for s,v in zip(('barco','avião','drone'),('verde','vermelho','roxo'))]
    view=probe.AttributeFrameReader(rows(pairs,('Meu gato é preto.','Meu gato se chama Alt.')),REGION).read('Qual nome do meu gato?')
    assert texts(view)=={'Meu gato é preto.'}
    assert view['answer'] is None and view['qualified'] is False
    assert view['factual_quality_status']=='NOT_EVALUATED'


def test_competing_teaching_retains_the_overgeneralized_frame_failure():
    data=rows();other=rows([('Qual nome do meu '+s+'?','Meu '+s+' é '+v+'.')
        for s,v in zip(('barco','avião','drone'),('verde','vermelho','roxo'))],('Meu gato é preto.',))
    data.append(dict(data[-1],source_id='boundary',sequence=len(data)+1,source_kind='assistant_generated'))
    data += [dict(r,source_id='other-'+r['source_id'],sequence=len(data)+i+1) for i,r in enumerate(other)]
    view=probe.AttributeFrameReader(data,REGION).read('Qual nome do meu gato?')
    # Mixing incompatible demonstrations also supports an overly broad frame.
    # Keep this false extra visible rather than treating conflict as truth.
    assert texts(view)=={'Meu gato se chama Alt.','Meu gato é preto.','Meu gato dorme no sofá.'}
    assert view['proposal_payload_id'] is None


def test_raw_symbol_renaming_retains_structural_transfer():
    data=rows();question='Qual nome do meu gato?'
    mapping={c:chr(1024+i) for i,c in enumerate(sorted(set(question+''.join(r['text'] for r in data))))}
    rename=lambda s:''.join(mapping[c] for c in s)
    view=probe.AttributeFrameReader([dict(r,text=rename(r['text'])) for r in data],REGION).read(rename(question))
    assert texts(view)=={rename('Meu gato se chama Alt.')}


def test_reference_metadata_is_masked_and_results_do_not_alias_reader_state():
    data=rows();before=probe.AttributeFrameReader(data,REGION).read('Qual nome do meu gato?')
    marked=[dict(r,expected='wrong',category='false',reply_to={'source_id':'hidden','sequence':0}) for r in data]
    reader=probe.AttributeFrameReader(marked,REGION)
    assert reader.read('Qual nome do meu gato?')==before
    result=reader.read('Qual nome do meu gato?');result['candidates'][0]['origins'].clear()
    result['candidates'][0]['witnesses'][0]['occurrences'].clear()
    assert reader.read('Qual nome do meu gato?')==before
    marked[0]['text']='external mutation'
    assert reader.read('Qual nome do meu gato?')==before


def test_every_witness_names_actual_adjacent_native_occurrences():
    data=rows();indexed={probe.address(r):i for i,r in enumerate(data)}
    view=probe.AttributeFrameReader(data,REGION).read('Qual nome do meu gato?')
    for candidate in view['candidates']:
        assert candidate['witnesses'] and candidate['support_is_factual_confidence'] is False
        for witness in candidate['witnesses']:
            assert witness['occurrences']
            for pair in witness['occurrences']:
                a=indexed[pair['source_origin']];b=indexed[pair['target_origin']]
                assert b==a+1 and data[a]['source_kind']==data[b]['source_kind']=='user_turn'


def test_casefold_collisions_preserve_raw_candidates_and_witnesses():
    observations = rows(facts=('Meu gato se chama Alt.', 'Meu GATO se chama Alt.'))
    reader = probe.AttributeFrameReader(observations, REGION)
    exact = reader.read('Qual nome do meu gato?')
    folded = reader.read('Qual nome do meu gato?', casefold=True)

    assert texts(exact) == {'Meu gato se chama Alt.'}
    assert texts(folded) == {'Meu gato se chama Alt.', 'Meu GATO se chama Alt.'}
    assert folded['matching_mode'] == 'unicode_casefold'
    assert folded['proposal_payload_id'] is None
    assert folded['learned_frames'] == exact['learned_frames']
    assert len({candidate['payload_id'] for candidate in folded['candidates']}) == 2
    assert all(candidate['witnesses'] == exact['candidates'][0]['witnesses']
               for candidate in folded['candidates'])
    assert {tuple(origin) for candidate in folded['candidates'] for origin in candidate['origins']} == {
        probe.address(row) for row in observations[-2:]
    }


def test_wording_probe_records_both_new_matches_and_remaining_abstentions():
    from trajectory_attribute_wording_probe import evaluate

    results = evaluate()
    assert len(results) == 24
    assert sum(result['exact']['exact_set'] for result in results) == 8
    assert sum(result['unicode_casefold']['exact_set'] for result in results) == 16
    assert sum(result['unicode_casefold']['true_positive'] for result in results) == 9
    assert all(result['unicode_casefold']['false_positive'] == 0 for result in results)
    assert all(result['unicode_casefold']['reason'] == 'NO_SUPPORTED_FRAME_CANDIDATE'
               for result in results if result['category'] == 'absent')


def test_projection_limits_refuse_complete_input_instead_of_truncating():
    data=rows()
    with pytest.raises(ValueError,match='64 rows'):
        probe.AttributeFrameReader([dict(data[0],sequence=i,source_id=str(i)) for i in range(65)],REGION)
    with pytest.raises(ValueError,match='4096 characters'):
        probe.AttributeFrameReader([dict(data[0],text='x'*4097)],REGION)
    with pytest.raises(ValueError): probe.AttributeFrameReader(data,'')
    with pytest.raises(ValueError): probe.AttributeFrameReader(data,REGION).read('')


@pytest.fixture
def library():
    path=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
    if not path.exists():
        if 'MEMORIA_NATIVE_LIBRARY' in os.environ: pytest.fail('Explicit native BDR library is missing')
        pytest.skip('Native integration runs in pinned-BDR CI')
    return path


def test_real_bdr_gate_preserves_improvement_and_semantic_failures(library):
    report=probe.gate(library)
    assert report['integrity_passed']==report['integrity_total']==14
    untaught,taught=report['stages']
    assert untaught['baseline_totals']==dict(cases=37,exact_set=13,true_positive=28,false_positive=51,false_negative=0)
    assert untaught['frame_totals']['true_positive']==0
    assert taught['frame_totals']==dict(cases=37,exact_set=30,true_positive=16,false_positive=0,false_negative=12)
    assert taught['baseline_totals']==dict(cases=37,exact_set=3,true_positive=28,false_positive=193,false_negative=0)
    assert report['retrieval_quality_status']=='FAIL_EXTRA_OR_MISSING_CONTENT'
    assert report['factual_quality_status']=='NOT_EVALUATED'
    absent=[c for c in taught['cases'] if c['category']=='absent_attribute']
    assert len(absent)==10 and all(c['frame']['exact_set'] for c in absent)
    assert all(c['view']['absence_proven'] is False for c in absent)


def test_cli_strict_quality_fails_and_writes_full_negative_evidence(library,tmp_path):
    output=tmp_path/'report.json'
    result=subprocess.run([sys.executable,str(Path(probe.__file__)),'--library',str(library),
        '--output',str(output),'--strict-quality'],capture_output=True,text=True)
    assert result.returncode==1,result.stderr
    report=json.loads(output.read_text());summary=json.loads(result.stdout)
    assert summary['full_report_sha256']==probe.fingerprint(report)
    assert len(report['stages'][1]['cases'])==37 and report['checks']


def test_opt_in_real_http_preserves_default_results_and_cold_provenance(library,tmp_path):
    from trajectory_local_mvp_gate import server,check_response
    state=tmp_path/'state';key='attribute-frame-test'
    def read(client,text,enabled=True):
        return check_response(client.post('/api/query',json=dict(text=text,attribute_frames=enabled)))
    def history(client): return check_response(client.get('/api/entries'))
    with server(library,state,key) as client:
        for row in rows(facts=('Meu gato se chama Alt.','Meu gato se chama Bia.','Meu gato dorme no sofá.')):
            check_response(client.post('/api/entries',json=dict(text=row['text'],source_kind=row['source_kind'])))
        before=history(client);baseline=read(client,'Qual nome do meu gato?',False)
        assert 'attribute_frames' not in baseline
        enabled=read(client,'Qual nome do meu gato?');frame=enabled.pop('attribute_frames')
        assert enabled==baseline
        assert texts(frame)=={'Meu gato se chama Alt.','Meu gato se chama Bia.'}
        assert frame['proposal_payload_id'] is None and frame['qualified'] is False
        assert read(client,'Qual a cor do meu gato?')['attribute_frames']['candidates']==[]
        upper = 'QUAL NOME DO MEU GATO?'
        assert read(client,upper)['attribute_frames']['candidates'] == []
        folded = check_response(client.post('/api/query', json=dict(
            text=upper, attribute_frames=True, attribute_frame_matching='unicode_casefold')))
        folded_view = folded.pop('attribute_frames')
        assert folded == read(client,upper,False)
        assert texts(folded_view) == {'Meu gato se chama Alt.', 'Meu gato se chama Bia.'}
        assert folded_view['matching_mode'] == 'unicode_casefold'
        assert folded_view['proposal_payload_id'] is None
        assert history(client)==before
    with server(library,state,key) as client:
        restored=read(client,'Qual nome do meu gato?')
        assert restored.pop('attribute_frames')==frame and restored==baseline
        restored_folded = check_response(client.post('/api/query', json=dict(
            text=upper, attribute_frames=True, attribute_frame_matching='unicode_casefold')))
        assert restored_folded['attribute_frames'] == folded_view
        assert history(client)==before


def test_http_agreement_mode_preserves_candidates_and_withholds_lone_proposal(library, tmp_path):
    from trajectory_attribute_paraphrase_probe import DOMAINS, fixture
    from trajectory_local_mvp_gate import server, check_response

    _, observations = fixture('names', 'mixed_one')
    request = dict(text=DOMAINS['names']['alternative'].format('monitor'),
                   attribute_frames=True)
    with server(library, tmp_path / 'state', 'frame-agreement-test') as client:
        for row in observations:
            check_response(client.post('/api/entries', json={
                key: row[key] for key in ('text', 'source_kind')
            }))
        before = check_response(client.get('/api/entries'))
        normal = check_response(client.post('/api/query', json=request))['attribute_frames']
        guarded = check_response(client.post('/api/query', json=dict(
            request, attribute_frame_require_agreement=True)))['attribute_frames']
        assert texts(guarded) == {'Meu monitor fica no escritório.'}
        assert guarded['candidates'] == normal['candidates']
        assert normal['proposal_payload_id'] is not None
        assert guarded['proposal_payload_id'] is None
        assert guarded['reason'] == 'UNSUPPORTED_MATCHING_FRAMES'
        assert len(guarded['frame_agreement']['matched_frame_ids']) == 2
        assert len(guarded['frame_agreement']['unsupported_frame_ids']) == 1
        assert not guarded['absence_proven']
        assert check_response(client.get('/api/entries')) == before


def test_http_comparison_detects_disagreement_and_reused_examples(library, tmp_path):
    from trajectory_attribute_paraphrase_probe import DOMAINS, fixture
    from trajectory_local_mvp_gate import server, check_response

    data = DOMAINS['names']
    _, observations = fixture('names', 'wrong_attribute')
    alternative = data['alternative'].format('rádio')
    canonical = data['canonical'].format('rádio')
    with server(library, tmp_path / 'state', 'frame-comparison-test') as client:
        for row in observations:
            check_response(client.post('/api/entries', json={
                key: row[key] for key in ('text', 'source_kind')
            }))
        before = check_response(client.get('/api/entries'))

        def compare(question, other):
            return check_response(client.post('/api/query', json=dict(
                text=question, attribute_frames=True, attribute_frame_require_agreement=True,
                attribute_frame_comparison_query=other)))['attribute_frames']

        different = compare(alternative, canonical)
        assert different['proposal_payload_id'] is None
        assert different['reason'] == 'DIFFERENT_PROPOSALS'
        assert texts(different) == {'Meu rádio fica na bancada.'}
        assert texts(different['comparison']) == {'Meu rádio se chama Faísca.'}
        repeated = compare(canonical, canonical)
        assert repeated['reason'] == 'SHARED_QUESTION_EXAMPLES'
        assert repeated['proposal_payload_id'] is None and repeated['qualified'] is False
        assert check_response(client.get('/api/entries')) == before
        invalid = client.post('/api/query', json=dict(
            text=canonical, attribute_frames=True, attribute_frame_comparison_query=' '))
        assert invalid.status_code == 422


def test_opt_in_http_limit_rejects_whole_projection_without_affecting_default_query(library,tmp_path):
    from fastapi.testclient import TestClient
    from trajectory_local_mvp import create_app
    headers={'X-Memoria-Key':'limit-test'}
    with TestClient(create_app(library=library,data_dir=tmp_path/'limited',api_key='limit-test')) as client:
        for i in range(65):
            assert client.post('/api/entries',headers=headers,json=dict(text='Observação '+str(i))).status_code==201
        before=client.get('/api/entries',headers=headers).json()
        assert client.post('/api/query',headers=headers,json=dict(text='Observação',attribute_frames=True)).status_code==413
        normal=client.post('/api/query',headers=headers,json=dict(text='Observação'))
        assert normal.status_code==200 and 'attribute_frames' not in normal.json()
        assert client.get('/api/entries',headers=headers).json()==before
