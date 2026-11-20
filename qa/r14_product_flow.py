#!/usr/bin/env python3
"""Android first-run UI proof. No capture, OCR, maps, or account setup exercised."""
import json
import sys

import r13_product_flow as baseline


def driver(r12):
    class Welcome(baseline.product_driver(r12)):
        def run(self):
            self.product_stages.update(direct_entry='NOT_RUN', optional_plan='NOT_RUN', reopen='NOT_RUN')
            ok = False
            try:
                self.launcher()
                self.state('welcome-terms', 'Seu primeiro acesso ao Vexo', 'Termos de uso')
                self.tap('accept-terms-check','Aceito os Termos de uso desta minuta.','entry-accept',scroll=True)
                self.tap('accept-terms-continue','Aceitar e continuar','entry-continue',scroll=True)
                self.product_stages['first_terms']='OBSERVED_AND_ACCEPTED'
                self.state('welcome-data','E aí, motora?','Entrar no Vexo','Configurar meu plano')
                self.product_stages['welcome_and_example']='PASS'
                self.tap('optional-plan-entry','Configurar meu plano')
                self.state('optional-plan-open','Já roda por aplicativo?')
                self.sh('input','keyevent','KEYCODE_BACK')
                self.state('welcome-return-from-plan','E aí, motora?','Entrar no Vexo')
                self.product_stages['optional_plan']='PASS'
                self.tap('welcome-direct-entry','Entrar no Vexo')
                self.state('welcome-direct-main','Treino OCR')
                self.no_projection('welcome-direct-main')
                self.product_stages['direct_entry']='PASS'
                self.sh('am','force-stop',self.pkg)
                self.sh('am','start','-n',self.pkg+'/com.trackingracing.AuroraActivity')
                self.state('welcome-reopen','Treino OCR')
                self.no_projection('welcome-reopen')
                self.product_stages['reopen']='PASS'
                ok = True
            except r12.Failure:
                self.ev('welcome-run','INCONCLUSIVE')
                try:
                    self.shot('welcome-inconclusive')
                except r12.Failure:
                    pass
            self.write('driver-result.json', json.dumps(dict(product_stages=self.product_stages), ensure_ascii=False)+'\n')
            return 0 if ok else 1

    return Welcome


if __name__ == '__main__':
    sys.exit(driver(baseline.r12_module())().run())
