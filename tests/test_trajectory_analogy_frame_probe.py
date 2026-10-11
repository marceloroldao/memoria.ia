from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from trajectory_analogy_frame_probe import learn_frames, checked_read, fixtures
from trajectory_native_bridge_probe import adapt
from trajectory_response_quality_probe import TrajectoryGenerationExperiment, encode


class AnalogyFrameTests(unittest.TestCase):
    def test_transfer_requires_observed_training_and_preserves_changed_relation_absence(self):
        for stage in ('no_scaffold', 'observed_scaffold'):
            memory, _ = adapt(dict(fixtures())[stage], 'unicode')
            result = checked_read(memory, encode('Qual nome do meu drone?', 'unicode'))
            self.assertEqual(result['hypothesis'], encode('Meu drone se chama Auri.', 'unicode')
                             if stage=='observed_scaffold' else None)
            for query in ('Qual potência do meu drone?', 'Qual nome do meu trem?',
                          'Qual nome do meu drone? Qual nome do meu robô?'):
                self.assertEqual(checked_read(memory, encode(query,'unicode'))['candidates'], ())

    def test_opaque_sequences_and_bijective_renaming_use_the_same_frame(self):
        for renamed in (False,True):
            transform = lambda xs: tuple(10000-x for x in xs) if renamed else xs
            memory = TrajectoryGenerationExperiment()
            for i in range(3):
                variable=(20+2*i,21+2*i)
                source=(1,2)+variable+(3,4)
                target=(5,6)+variable+(7,8)+(30+2*i,31+2*i)+(9,10)
                memory.observe(transform(source),observation_id=f'{i}:s',stream_id=str(i))
                memory.observe(transform(target),observation_id=f'{i}:t',stream_id=str(i))
            fact=(5,6,80,81,7,8,90,91,9,10)
            memory.observe(transform(fact),observation_id='isolated',stream_id='isolated')
            result=checked_read(memory,transform((99,1,2,80,81,3,4)))
            self.assertEqual(result['hypothesis'],transform(fact))
            self.assertIsNone(checked_read(memory,transform((1,2,82,83,3,4)))['hypothesis'])

    def test_payload_repetition_cannot_supply_three_distinct_variables(self):
        rows=dict(fixtures())['observed_scaffold'][-6:-2]
        memory,_=adapt(rows,'unicode')
        for i in range(4):
            memory.observe(encode(rows[0]['text'],'unicode'),observation_id=f'repeat:{i}:s',stream_id=f'r{i}')
            memory.observe(encode(rows[1]['text'],'unicode'),observation_id=f'repeat:{i}:t',stream_id=f'r{i}')
        self.assertEqual(learn_frames(memory),())

    def test_assistant_barrier_excludes_the_training_pair_and_generated_destination(self):
        memory,_=adapt(dict(fixtures())['assistant_barrier'],'unicode')
        self.assertEqual(learn_frames(memory),())
        valid,_=adapt(dict(fixtures())['observed_scaffold'],'unicode')
        result=checked_read(valid,encode('Qual nome do meu drone?','unicode'))
        self.assertNotIn(encode('Meu drone se chama Falso.','unicode'),
                         {c['output'] for c in result['candidates']})

    def test_competing_destinations_and_competing_frames_both_remain_visible(self):
        for stage, expected in [('isolated_conflict',('Meu drone se chama Auri.','Meu drone se chama Boreal.')),
                                ('competing_frames',('Meu drone se chama Auri.','Meu drone é azul.'))]:
            memory,_=adapt(dict(fixtures())[stage],'unicode')
            result=checked_read(memory,encode('Qual nome do meu drone?','unicode'))
            self.assertIsNone(result['hypothesis'])
            self.assertEqual({c['output'] for c in result['candidates']},
                             {encode(text,'unicode') for text in expected})
            self.assertTrue(all(c['witnesses'] for c in result['candidates']))

    def test_captures_and_unique_copied_variable_are_required(self):
        rows=dict(fixtures())['observed_scaffold'][-6:]
        separate=[dict(r,hierarchy_id=r['source_id']) for r in rows]
        memory,_=adapt(separate,'unicode')
        self.assertEqual(learn_frames(memory),())
        repeated=[dict(r,text=r['text'].replace(' se chama ', ' '+('barco','avião','sensor')[i//2]+' se chama '))
                  if i%2 else r for i,r in enumerate(rows)]
        memory,_=adapt(repeated,'unicode')
        self.assertEqual(learn_frames(memory),())
