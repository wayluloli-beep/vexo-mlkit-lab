#!/usr/bin/env python3
"""R14 native-pixel association QA on the existing private, clean API 35 runner."""
import hashlib
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import r13_product_flow as baseline


CARD_TAG = re.compile(
    r'\bVexoLocalOcr\s*:\s*(pixels src=(pixelcopy|web_draw)|parsed kind=(pop|negocia)|'
    r'dispatched kind=offer|accepted kind=offer) cap=([0-9]{1,18}) card=([0-9]{1,18}-[0-9]{1,6})\s*$'
)


WITNESS_TAG = re.compile(r"\bVexoLocalOcr\s*:\s*witness=[a-z_]{1,30} card=[0-9]{1,18}-[0-9]{1,6} t=[0-9]{1,18}\s*$")

def accepted_chains(log):
    """Only complete, ordered chains with a single card token per native capture."""
    records, conflicting, complete = {}, set(), {}
    for line in log.splitlines():
        event = CARD_TAG.search(line)
        if not event:
            continue
        name, source, kind, cap, card = event.groups()
        record = records.setdefault(cap, {'cap': int(cap), 'card': card})
        if card != record['card']:
            conflicting.add(cap)
        elif source:
            record['pixels'] = source
        elif kind and 'pixels' in record:
            record['kind'] = kind
        elif name == 'dispatched kind=offer' and 'kind' in record:
            record['dispatch'] = True
        elif name == 'accepted kind=offer' and record.get('dispatch'):
            complete[cap] = {key: record[key] for key in ('cap', 'card', 'pixels', 'kind')}
    return [chain for cap, chain in complete.items() if cap not in conflicting]


def exact_group(root, pkg, marker):
    keys = ('text', 'content-desc')
    marker = baseline.norm(marker)

    def visible(node):
        return node.get('package') == pkg and node.get('visible-to-user') != 'false'

    groups = []
    for node in root.iter('node'):
        labels = [baseline.norm(node.get(key, '')) for key in keys]
        if not visible(node) or not any(label == marker or label.startswith(marker + ' ') for label in labels):
            continue
        groups.append(baseline.norm(' '.join(
            x for child in node.iter('node') if visible(child) for key in keys if (x := child.get(key, ''))
        )))
    # Never merge an unrelated card whose fare happened to be visible elsewhere in the WebView.
    return groups[0] if len(groups) == 1 else ''


def visible_offer(root, pkg, kind, price):
    card = exact_group(root, pkg, 'Oferta 99' + kind)
    return bool(re.search(r'\br\$\s*' + price.replace('.', '[,.]') + r'(?!\d)', card))


def driver(r12):
    class R14(baseline.product_driver(r12)):
        def __init__(self):
            super().__init__()
            self.product_stages.update(local_card_1_metrics='NOT_RUN', local_card_1_native='NOT_RUN',
                                       local_next_card='NOT_RUN', local_cleanup='NOT_RUN',
                                       external_attempt='NOT_RUN')

        def tagged_local_log(self):
            pid = self.sh('pidof', '-s', self.pkg, timeout=12).strip()
            if not pid.isdecimal():
                raise r12.Failure('Vexo app process not available to read local log')
            raw = self.cmd('logcat', '-d', '-v', 'monotonic', '--pid='+pid, '-t', '2500',
                           '-s', 'VexoLocalOcr:I', '*:S', timeout=17).decode('utf-8', 'replace')
            clean = ''.join(row+'\n' for row in raw.splitlines() if CARD_TAG.search(row) or WITNESS_TAG.search(row))
            self.write('local-ocr.log', clean)
            return accepted_chains(clean)

        def checkpoint(self, label, key, **fields):
            self.write(label+'.xml', (self.out/(key+'.xml')).read_bytes())
            screenshot = self.shot(label)
            self.ev(label, 'OBSERVED', xml=label+'.xml', png=screenshot.name,
                    sha256=hashlib.sha256(screenshot.read_bytes()).hexdigest(), **fields)

        def first_pop_native(self):
            first = [chain for chain in self.tagged_local_log()
                     if chain['card'].endswith('-1') and chain['kind'] == 'pop']
            if first and len({chain['card'] for chain in first}) == 1:
                self.product_stages['local_card_1_native'] = 'PASS'
                self.ev('local-card-1-native', 'PASS', **first[0])
                return first[0]
            self.product_stages['local_card_1_native'] = 'INCONCLUSIVE'
            self.ev('local-card-1-native', 'INCONCLUSIVE', reason='no unique accepted Pop chain at first card step')
            return None

        def local(self):
            self.tap('local-open-training', 'Treino OCR')
            self.state('local-training-sheet', 'Ajustar treino', 'Iniciar treino')
            self.no_projection('local-before')
            root, key, _ = self.product_observe('local-before-ui', lambda r: baseline.click_of(r, self.pkg, 'Iniciar treino'))
            self.checkpoint('local-before', key)
            if exact_group(root, self.pkg, 'Balão OCR local'):
                raise r12.Failure('local balloon visible before starting fresh training')
            self.cmd('logcat', '-c', timeout=14)
            self.tap('local-start', 'Iniciar treino')
            seen = set()
            next_stale = False

            def observe(root):
                nonlocal next_stale
                app = self.content(root)
                scope = exact_group(root, self.pkg, 'Balão OCR local')
                first = ('oferta 1 de 6' in app and visible_offer(root, self.pkg, 'Pop', '8.30'))
                second = ('oferta 2 de 6' in app and visible_offer(root, self.pkg, 'Negocia', '12.64'))
                old_metrics = baseline.local_metrics(scope)
                if first and old_metrics and 'local-result' not in seen:
                    return 'local-result'
                if second and old_metrics and not next_stale:
                    next_stale = True
                    return 'local-next-stale'
                if second and scope and 'local-next-card' not in seen:
                    return 'local-next-card'
                if first and 'local-first-card' not in seen:
                    return 'local-first-card'
                if 'aguardando leitura' in scope and 'local-idle' not in seen:
                    return 'local-idle'
                if re.search(r'\boferta [3-6] de 6\b', app) or ('treino com ocr' in app and 'ofertas exibidas' in app):
                    return 'past-second'
                return None

            while True:
                _, key, state = self.product_observe('local-result-ui', observe, seconds=27)
                if state == 'past-second':
                    break
                self.checkpoint(state, key)
                seen.add(state)
                if state == 'local-result':
                    self.product_stages['local_card_1_metrics'] = 'PASS'
            self.no_projection('local-result')
            chain = self.first_pop_native()
            if self.product_stages['local_card_1_metrics'] == 'NOT_RUN':
                self.product_stages['local_card_1_metrics'] = 'INCONCLUSIVE'
            self.product_stages['local_next_card'] = ('FAIL_OTHER_SCENE' if next_stale else 'PASS'
                if 'local-result' in seen and 'local-next-card' in seen else 'INCONCLUSIVE')
            if (self.product_stages['local_card_1_native'] == 'PASS'
                    and self.product_stages['local_card_1_metrics'] == 'PASS'
                    and self.product_stages['local_next_card'] == 'PASS'):
                self.product_stages['local_ocr'] = 'PASS'
                self.ev('local-real-ocr', 'PASS', xml='local-result.xml', png='local-result.png',
                        next_xml='local-next-card.xml', native=chain, external_projection=False)
            else:
                self.product_stages['local_ocr'] = 'FAIL_OTHER_SCENE' if next_stale else 'INCONCLUSIVE'
                self.ev('local-real-ocr', self.product_stages['local_ocr'],
                        metrics=self.product_stages['local_card_1_metrics'],
                        native=self.product_stages['local_card_1_native'],
                        next_card=self.product_stages['local_next_card'])

        def return_from_local(self):
            def inspect(root):
                app = self.content(root)
                if (stop := baseline.click_of(root, self.pkg, 'Encerrar treino')):
                    return 'stop', stop
                if 'treino com ocr' in app and (close := baseline.click_of(root, self.pkg, 'Voltar')):
                    return 'summary', close
                if ('ajustar treino' in app or 'iniciar treino' in app) and (
                    close := baseline.click_of(root, self.pkg, 'Fechar')):
                    return 'options', close
                if baseline.click_of(root, self.pkg, 'Treino OCR'):
                    return 'main', None
                return None

            for _ in range(4):
                _, key, (state, target) = self.product_observe('local-safe-exit', inspect, seconds=20)
                if state == 'main':
                    self.no_projection('local-stopped')
                    self.checkpoint('local-training-stopped', key)
                    return
                self.act(key, target, 'local-exit-'+state)
            raise r12.Failure('did not return from training via visible Android UI')

        def consent(self):
            with self.clip('product-flow'):
                self.launcher()
                self.first_entry()
                try:
                    self.navigation()
                except r12.Failure as exc:
                    self.errs.append(('central-navigation', str(exc)))
                    self.ev('central-navigation', 'INCONCLUSIVE', reason=str(exc)[:300])
                try:
                    self.local()
                except r12.Failure as exc:
                    self.errs.append(('local-real-ocr', str(exc)))
                    self.product_stages['local_ocr'] = 'INCONCLUSIVE'
                    self.ev('local-real-ocr', 'INCONCLUSIVE', reason=str(exc)[:300])
                finally:
                    if self.product_stages['local_ocr'] != 'PASS':
                        try:
                            self.shot('local-inconclusive')
                        except r12.Failure as exc:
                            self.ev('local-evidence', 'INCONCLUSIVE', reason=str(exc)[:300])
                        if self.product_stages['local_card_1_native'] == 'NOT_RUN':
                            try:
                                self.first_pop_native()
                            except r12.Failure as exc:
                                self.ev('local-card-1-native', 'INCONCLUSIVE', reason=str(exc)[:300])
                    try:
                        self.return_from_local()
                        self.product_stages['local_cleanup'] = 'PASS'
                    except r12.Failure as exc:
                        self.errs.append(('local-cleanup', str(exc)))
                        self.product_stages['local_cleanup'] = 'INCONCLUSIVE'
                        self.ev('local-cleanup', 'INCONCLUSIVE', reason=str(exc)[:300])
            self.product_ok = (self.product_stages['first_terms'] == 'OBSERVED_AND_ACCEPTED' and
                               self.product_stages['local_ocr'] == 'PASS' and
                               self.product_stages['local_cleanup'] == 'PASS')
            self.product_stages['external_attempt'] = 'ATTEMPTED'
            self.ev('external-independent', 'ATTEMPTED')
            if self.product_stages['local_cleanup'] != 'PASS':
                self.no_projection('before-independent-relaunch')
                self.sh('am','force-stop',self.pkg)
                self.launcher()
                self.state('external-reopened-main','Treino OCR',seconds=55)
                self.ev('external-isolation', 'PASS')
            self.central()
            # Retain the exact R12 permission, native consent, FGS, presenter and stop path.
            r12.Run.consent(self)
            self.product_stages['external_attempt'] = 'PASS'

        def run(self):
            rc = r12.Run.run(self)
            path = self.out/'driver-result.json'
            status = json.loads(path.read_text())
            status.update(product_real_ocr_chain=self.product_ok, product_stages=self.product_stages,
                          motion_review='MANUAL_FRAME_REVIEW_REQUIRED',
                          same_apk_witness='device-apks.sha256')
            self.write(path.name, json.dumps(status, ensure_ascii=False, indent=2)+'\n')
            return rc or int(not self.product_ok)

    return R14


if __name__ == '__main__':
    sys.exit(driver(baseline.r12_module())().run())
