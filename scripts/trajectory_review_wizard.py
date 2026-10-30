#!/usr/bin/env python3
"""Portuguese terminal workflow over the existing explicit local review operations."""
import argparse
import json
from pathlib import Path
from uuid import uuid4

from trajectory_feedback_session import FeedbackSession
from trajectory_region_evidence_probe import fingerprint
from trajectory_review_outcomes import compare_receipts


def literal(value):
    return json.dumps(str(value),ensure_ascii=False)


class ReviewWizard:
    def __init__(self,session,scope,actor,read=input,write=print,new_id=None):
        if not isinstance(actor,str) or not actor.strip() or len(actor)>128:
            raise ValueError('Identidade declarada deve ter de 1 a 128 caracteres.')
        self.session=session;self.scope=scope;self.actor=actor
        self.read=read;self.write=write;self.new_id=new_id or (lambda:uuid4().hex)
        self.call('history')  # Validate namespace before asking for inputs.

    def call(self,op,**values):
        return self.session.execute(dict(op=op,scope=self.scope,**values))['result']

    def text(self,prompt,maximum):
        while True:
            value=self.read(prompt)
            if value.strip() and len(value)<=maximum:return value
            self.write(f'Digite conteúdo não vazio com até {maximum} caracteres.')

    def option(self,prompt,allowed):
        while True:
            value=self.read(prompt).strip().lower()
            if value in allowed:return value
            self.write('Opção inválida. Escolha uma das opções exibidas.')

    def number(self,prompt,maximum):
        return int(self.option(prompt,{str(i) for i in range(1,maximum+1)}))

    def show_reading(self,reading):
        self.write('Candidatas disponíveis; adequação factual ainda não avaliada:')
        for candidate in reading['available_candidates']:
            self.write('  '+literal(candidate['text']))
            self.write('  Sequências de origem: '+', '.join(str(origin[2]) for origin in candidate['origins']))
        if not reading['available_candidates']:self.write('  Nenhuma.')
        if reading['withheld_candidates']:
            self.write(f'Suspensas por feedback: {len(reading["withheld_candidates"])}. O conteúdo bruto foi preservado.')
            for candidate in reading['withheld_candidates']:self.write('  '+literal(candidate['text']))
        for finding in reading['diagnosis']['findings']:
            self.write(finding['message']+' '+finding['guidance'])
        missing=sorted({s['text'] for frame in reading['diagnosis']['frames'] for s in frame.get('unwitnessed_symbols',[])})
        if missing:self.write('Símbolos sem mapa em algumas rotas: '+', '.join(literal(s) for s in missing))

    def register_entry(self):
        text=self.text('Conteúdo observado: ',2000)
        kind=self.option('Origem: [u] relato/observação declarada; [g] conteúdo gerado; [p] pular: ',{'u','g','p'})
        if kind=='p':return
        saved=self.call('observe',event_id='wizard-entry:'+self.new_id(),text=text,
                        source_kind='user_turn' if kind=='u' else 'assistant_generated')
        self.write('Entrada registrada: '+saved['status'])

    def collect_offers(self):
        offers=[]
        count=self.number('Quantos conjuntos de exemplos? [1-8]: ',8)
        for i in range(count):
            self.write(f'Conjunto {i+1}; a origem declarada não é autenticada.')
            provenance=self.text('Origem declarada: ',256)
            examples=[]
            for _ in range(self.number('Quantos pares neste conjunto? [1-3]: ',3)):
                examples.append(dict(source_text=self.text('Texto de origem/pergunta: ',2000),
                                     target_text=self.text('Conteúdo associado: ',2000)))
            offers.append(dict(offer_id=f'example-{i+1}',provenance=provenance,examples=examples))
        return offers

    def show_offers(self,review):
        self.write('Exemplos oferecidos; a marcação estrutural não garante melhora:')
        for i,item in enumerate(review['offers'],1):
            offer=item['offer']
            self.write(f'{i}. Origem declarada: '+literal(offer.get('provenance','')))
            for example in offer['examples']:
                self.write('  Origem: '+literal(example['source_text']))
                self.write('  Conteúdo: '+literal(example['target_text']))
            self.write('  Relação com lacuna indicada: '+('sim' if item['structurally_related_to_reported_gap'] else 'não marcada; pode ser útil'))

    def review(self):
        query=self.text('Pergunta a avaliar: ',4000)
        offers=self.collect_offers()
        opened=self.call('open_review',text=query,offers=offers)['event']
        self.write('Revisão preservada em auditoria; os exemplos ainda não foram incorporados.')
        self.show_reading(opened['reviewed_result']);self.show_offers(opened['reviewed_result']['example_review'])
        count=len(offers)
        option=self.option(f'Escolha [1-{count}], [d] adiar, [r] rejeitar todos ou [s] sair sem decidir: ',
                           {str(i) for i in range(1,count+1)}|{'d','r','s'})
        if option=='s':return
        choice='defer' if option=='d' else 'reject_all' if option=='r' else 'select'
        decision_id='wizard-decision:'+self.new_id()
        result=self.call('record_review_decision',receipt_id=opened['receipt_id'],decision_id=decision_id,actor_id=self.actor,
                         choice=choice,offer_id=offers[int(option)-1]['offer_id'] if choice=='select' else None,
                         reason=self.text('Justificativa da decisão: ',2000))
        self.write('Decisão registrada: '+literal(decision_id))
        self.finish(result['event'],opened)

    def incorporation_plan(self,decision,binding,kind):
        offer=next(r['offer'] for r in binding['reviewed_result']['example_review']['offers'] if r['offer']['offer_id']==decision['offer_id'])
        planned=[]
        for i,example in enumerate(offer['examples']):
            for suffix,text,origin in (('q',example['source_text'],kind),('a',example['target_text'],kind),
                                       ('barrier','Intervalo observado.','assistant_generated')):
                planned.append(dict(event_id=f'wizard-apply:{decision["decision_id"]}:{i}:{suffix}',text=text,source_kind=origin))
        rows=self.call('history')['entries'];existing={r['source_id']:r for r in rows};pending=[]
        for entry in planned:
            previous=existing.get('session-observation:'+fingerprint(entry['event_id']))
            if previous:
                if previous['text']!=entry['text'] or previous['source_kind']!=entry['source_kind']:
                    raise ValueError('A retomada exige a mesma origem e os mesmos textos já registrados.')
            else:pending.append(entry)
        if len(rows)+len(pending)>64 or sum(len(r['text']) for r in rows)+sum(len(r['text']) for r in pending)>4096:
            raise ValueError('O conjunto inteiro excede o limite da sessão; nenhum novo par foi registrado.')
        return planned

    def finish(self,decision,binding):
        if decision['choice']=='select':
            kind=self.option('Registro separado: [u] incorporar como observação declarada; [g] registrar como gerado; [p] pular: ',{'u','g','p'})
            if kind!='p':
                plan=self.incorporation_plan(decision,binding,'user_turn' if kind=='u' else 'assistant_generated')
                for entry in plan:self.call('observe',**entry)
                self.write('Pares registrados como observações declaradas; adequação factual não avaliada.' if kind=='u' else
                           'Conteúdo registrado como gerado; permanece excluído da aprendizagem.')
        offers=[r['offer'] for r in binding['reviewed_result']['example_review']['offers']]
        after=self.call('open_review',text=binding['query'],offers=offers)['event']
        self.write('Leitura posterior:');self.show_reading(after['reviewed_result'])
        comparison=compare_receipts(binding,after)
        for label,key in (('Brutas','raw'),('Disponíveis','available'),('Suspensas','withheld')):
            delta=comparison[key]
            self.write(f'{label}: {delta["before_count"]} → {delta["after_count"]}; acrescentadas {len(delta["added_ids"])}; retiradas {len(delta["removed_ids"])}.')
        self.write('Essas diferenças não certificam melhora nem causalidade.')
        option=self.option('Avaliação declarada: [a] ajudou; [i] igual; [p] piorou; [d] dúvida; [s] registrar depois: ',{'a','i','p','d','s'})
        if option=='s':
            self.write('Resultado adiado. Retome a decisão pelo identificador exibido.');return
        result=self.call('record_review_outcome',decision_id=decision['decision_id'],after_receipt_id=after['receipt_id'],
                         outcome_id='wizard-outcome:'+self.new_id(),actor_id=self.actor,
                         judgement={'a':'helped','i':'unchanged','p':'worsened','d':'uncertain'}[option],
                         reason=self.text('Justificativa da avaliação: ',2000))
        self.write('Resultado registrado: '+literal(result['event']['outcome_id']))

    def list_decisions(self):
        audit=self.call('review_decisions')
        self.write('Decisões preservadas:')
        for row in audit['decisions']:
            event=row['event']
            self.write(literal(event['decision_id'])+' | '+event['choice']+' | operador declarado '+literal(event['actor_id']))
        if not audit['decisions']:self.write('  Nenhuma.')

    def list_entries(self):
        rows=self.call('history')['entries']
        self.write('Entradas da região; sequências e origem declarada:')
        for row in rows:self.write(f'{row["sequence"]} | {row["source_kind"]} | '+literal(row['text']))
        if not rows:self.write('  Nenhuma.')

    def resume(self):
        identity=self.text('ID da decisão a retomar: ',128)
        audit=self.call('review_decisions')
        matches=[r['event'] for r in audit['decisions'] if r['event']['decision_id']==identity]
        if len(matches)!=1:raise ValueError('Decisão não encontrada neste escopo.')
        decision=matches[0]
        if decision['actor_id']!=self.actor:raise ValueError('Use a mesma identidade declarada da decisão; ela não é autenticada.')
        binding=next(r['event'] for r in audit['receipts'] if r['event']['receipt_id']==decision['receipt_id'])
        self.write('Retomada de decisão histórica: '+literal(identity))
        self.show_reading(binding['reviewed_result']);self.show_offers(binding['reviewed_result']['example_review'])
        offers=[r['offer'] for r in binding['reviewed_result']['example_review']['offers']]
        self.write('Confira também a leitura atual antes de registrar exemplos:')
        self.show_reading(self.call('review_examples',text=binding['query'],offers=offers))
        self.finish(decision,binding)

    def run(self):
        self.write('Memoria.ia — avaliação local com decisões explícitas. Identidade declarada, sem autenticação.')
        while True:
            try:
                option=self.option('[1] registrar entrada; [2] revisar; [3] listar decisões; [4] retomar; [5] ver entradas; [0] sair: ',{'0','1','2','3','4','5'})
                if option=='0':return
                {'1':self.register_entry,'2':self.review,'3':self.list_decisions,'4':self.resume,'5':self.list_entries}[option]()
            except ValueError as error:
                self.write('Operação recusada: '+str(error))
            except (EOFError,KeyboardInterrupt):
                self.write('Sessão encerrada. Decisões já confirmadas podem ser retomadas.');return


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--library',type=Path,required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    parser.add_argument('--scope',default='principal')
    parser.add_argument('--actor',required=True)
    args=parser.parse_args()
    try:
        with FeedbackSession(args.library,args.data_dir) as session:
            ReviewWizard(session,args.scope,args.actor).run()
    except ValueError as error:
        parser.exit(1,'Operação recusada: '+str(error)+'\n')
    except RuntimeError as error:
        parser.exit(1,'Falha: '+str(error)+'\nConfira o histórico antes de retomar; uma etapa pode não ter sido confirmada.\n')


if __name__=='__main__':main()
