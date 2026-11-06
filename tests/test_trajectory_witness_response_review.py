import copy
import itertools
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from trajectory_borrowed_map_probe import fixture
from trajectory_feedback_portuguese_probe import score
from trajectory_feedback_session import FeedbackSession
from trajectory_review_wizard import ReviewWizard
from trajectory_witness_requests_probe import scripted_response
from trajectory_witness_response_review import current_requests,open_response,response_origin


class WitnessResponseReviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.library=Path(os.environ.get('MEMORIA_NATIVE_LIBRARY','build/trajectory-native/libmemoria_mobile.so')).resolve()
        if not cls.library.exists():raise unittest.SkipTest('native library required')

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.directory=Path(self.temp.name);self.session=FeedbackSession(self.library,self.directory);self.addCleanup(self.session.close)
        self.fixture=fixture('humidity',20261101,'uppercase','two_anchors','switched_map')
        self.scope=self.fixture['scope'];self.query=self.fixture['queries'][0]['text'];self.ids=itertools.count(1)
        for row in self.fixture['rows']:self.session.execute(dict(op='observe',scope=self.scope,**row))
        self.request=current_requests(self.session,self.scope,self.query)['requests'][0]

    def call(self,op,**values):return self.session.execute(dict(op=op,scope=self.scope,**values))['result']
    def history(self):return self.call('history')
    def response(self,arm):return scripted_response(self.fixture,self.request,arm)[1]['text']
    def opened(self,arm='observed',kind='user_turn'):
        return open_response(self.session,self.scope,self.query,self.request['request_id'],self.response(arm),kind)
    def decide(self,opened,choice,identity='decision'):
        receipt=opened['review_receipt'];offer=receipt['event']['reviewed_result']['example_review']['offers'][0]['offer']
        return self.call('record_review_decision',receipt_id=receipt['event']['receipt_id'],decision_id=identity,actor_id='operator',
                         choice=choice,offer_id=offer['offer_id'] if choice=='select' else None,reason='Programmed review test.')
    def wizard(self,answers):
        answers=iter(answers);output=[]
        def read(prompt):
            output.append(prompt)
            try:return next(answers)
            except StopIteration:raise EOFError
        wizard=ReviewWizard(self.session,self.scope,'operator',read=read,write=output.append,new_id=lambda:f'review-{next(self.ids)}')
        return wizard,output

    def test_receipt_binds_source_content_and_request_without_learning_and_replays_after_restart(self):
        before=self.history();reading=self.call('query',text=self.query);opened=self.opened()
        receipt=opened['review_receipt']['event'];offer=receipt['reviewed_result']['example_review']['offers'][0]['offer']
        binding=response_origin(offer)
        self.assertEqual(binding['request_id'],self.request['request_id']);self.assertEqual(binding['source_kind'],'user_turn')
        self.assertEqual(offer['examples'][0],dict(source_text=self.request['source_text'],target_text=self.response('observed')))
        self.assertEqual(self.history(),before);self.assertEqual(self.call('query',text=self.query),reading)
        self.assertEqual(self.opened()['review_receipt']['status'],'EXACT_REPLAY')
        audit=self.call('review_decisions');self.session.close()
        with FeedbackSession(self.library,self.directory) as cold:
            again=open_response(cold,self.scope,self.query,self.request['request_id'],self.response('observed'),'user_turn')
            self.assertEqual(again['review_receipt']['status'],'EXACT_REPLAY')
            self.assertEqual(cold.execute(dict(op='review_decisions',scope=self.scope))['result'],audit)

    def test_select_defer_and_reject_only_record_decisions(self):
        before=self.history()
        for choice in ('select','defer','reject_all'):
            opened=self.opened('incorrect_observation');self.decide(opened,choice,choice)
            self.assertEqual(self.history(),before)
        self.assertEqual(len(self.call('review_decisions')['decisions']),3)
        self.assertEqual(current_requests(self.session,self.scope,self.query)['requests'],[self.request])

    def test_invalid_source_request_query_scope_and_text_write_no_audit(self):
        before=self.history();audit=self.call('review_decisions')
        arguments=dict(session=self.session,scope=self.scope,query=self.query,request_id=self.request['request_id'],response_text='reply',source_kind='user_turn')
        for changes in (dict(source_kind='unknown'),dict(request_id='missing'),dict(query='zzzzzzz'),dict(scope='foreign'),dict(response_text=' '),dict(response_text='x'*2001)):
            with self.subTest(changes=list(changes)):
                with self.assertRaises(ValueError):open_response(**dict(arguments,**changes))
                self.assertEqual(self.history(),before);self.assertEqual(self.call('review_decisions'),audit)

    def test_stale_receipt_cannot_authorize_a_new_decision(self):
        opened=self.opened();self.call('observe',event_id='later',text='Observação posterior.')
        audit=self.call('review_decisions')
        with self.assertRaisesRegex(ValueError,'stale'):self.decide(opened,'select')
        self.assertEqual(self.call('review_decisions'),audit)

    def test_metadata_or_content_tampering_is_rejected(self):
        opened=self.opened(kind='assistant_generated');offer=opened['review_receipt']['event']['reviewed_result']['example_review']['offers'][0]['offer']
        self.assertIsNone(response_origin(dict(offer,offer_id='ordinary-example',provenance='witness-response-v1|literal caller note')))
        for changed in (dict(provenance=offer['provenance'].replace('assistant_generated','user_turn')),
                        dict(examples=[dict(source_text=self.request['source_text'],target_text='different')]),
                        dict(provenance='witness-response-v1|invalid')):
            with self.assertRaises(ValueError):response_origin(dict(offer,**changed))

    def test_generated_response_cannot_be_reclassified_on_initial_apply_or_resume(self):
        before=self.history();content=self.response('generated')
        wizard,output=self.wizard(['7',self.query,'1',content,'g','1','Review test.','u','p','s','0']);wizard.run()
        self.assertIn('Registro separado: [g] registrar como gerado; [p] pular: ',output)
        self.assertTrue(any('Opção inválida' in row for row in output));self.assertEqual(self.history(),before)
        decision=self.call('review_decisions')['decisions'][0]['event'];self.assertEqual(self.call('review_outcomes')['outcomes'],[])
        receipt=self.call('review_decisions')['receipts'][0]['event']
        with self.assertRaisesRegex(ValueError,'só pode ser registrada como gerada'):wizard.incorporation_plan(decision,receipt,'user_turn')
        wizard,output=self.wizard(['4',decision['decision_id'],'u','p','s','0']);wizard.run()
        self.assertTrue(any('Opção inválida' in row for row in output));self.assertEqual(self.history(),before)
        wizard,output=self.wizard(['4',decision['decision_id'],'g','d','Generated content remains excluded.','0']);wizard.run()
        after=self.history();self.assertEqual(len(after['entries']),len(before['entries'])+3)
        self.assertTrue(all(row['source_kind']=='assistant_generated' for row in after['entries'][-3:]))
        self.assertEqual(current_requests(self.session,self.scope,self.query)['requests'],[self.request])
        self.assertEqual(len(self.call('review_outcomes')['outcomes']),1)

    def test_incorrect_declared_observation_still_can_teach_wrong_route_after_explicit_application(self):
        opened=self.opened('incorrect_observation');before=self.history();decision=self.decide(opened,'select')['event']
        self.assertEqual(self.history(),before)
        wizard,_=self.wizard(['u','d','Uncertain programmed observation.']);wizard.finish(decision,opened['review_receipt']['event'])
        for query in self.fixture['queries'][:2]:
            result=self.session.execute(dict(op='query',scope=self.scope,text=query['text']))
            judged=score(result,query['expected']);self.assertFalse(judged['exact']);self.assertEqual(judged['extra'],1);self.assertEqual(judged['missing'],1)

    def test_real_terminal_can_preserve_a_response_without_manual_json_or_request_id(self):
        before=self.history();self.session.close()
        script=Path(__file__).resolve().parents[1]/'scripts'/'trajectory_review_wizard.py'
        answers=['7',self.query,'1',self.response('incorrect_observation'),'u','d','Need evidence.','d','Not verified.','0']
        run=subprocess.run([sys.executable,str(script),'--library',str(self.library),'--data-dir',str(self.directory),
                            '--scope',self.scope,'--actor','operator'],input='\n'.join(answers)+'\n',text=True,capture_output=True,check=True)
        self.assertIn('Revisão preservada em auditoria',run.stdout)
        with FeedbackSession(self.library,self.directory) as cold:
            self.assertEqual(cold.execute(dict(op='history',scope=self.scope))['result'],before)
            self.assertEqual(len(cold.execute(dict(op='review_outcomes',scope=self.scope))['result']['outcomes']),1)
