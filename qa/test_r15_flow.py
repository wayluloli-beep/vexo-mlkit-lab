import unittest
import r14_product_flow as flow

accepted_chains = flow.accepted_chains
matches_local_metrics = flow.matches_local_metrics


class LocalOcrEvidenceTest(unittest.TestCase):
    def test_negocia_metrics_do_not_match_stale_pop_at_same_per_km_rate(self):
        pop = 'R$ 1,34/km R$ 29,29/hr'
        neg = 'R$ 1,34/km R$ 30,34/hr'
        self.assertTrue(matches_local_metrics(pop, 'pop'))
        self.assertFalse(matches_local_metrics(pop, 'negocia'))
        self.assertTrue(matches_local_metrics(neg, 'negocia'))
        self.assertFalse(matches_local_metrics(neg, 'pop'))
        self.assertFalse(matches_local_metrics('Aguardando leitura', 'negocia'))

    def test_acceptance_requires_same_card_and_measures_capture_to_ui(self):
        def line(value):
            return f'VexoLocalOcr: {value}'
        rows = [line('pixels src=pixelcopy cap=100 card=1-1'),
                line('parsed kind=pop cap=100 card=1-1'),
                line('dispatched kind=offer cap=100 card=1-1'),
                line('accepted kind=offer cap=100 card=1-1'),
                line('witness=ui_accepted card=1-1 t=350 cap=100'),
                line('pixels src=pixelcopy cap=400 card=1-3'),
                line('parsed kind=negocia cap=400 card=1-3'),
                line('dispatched kind=offer cap=400 card=1-3'),
                line('accepted kind=offer cap=400 card=1-1')]
        self.assertEqual(accepted_chains('\n'.join(rows)), [
            {'cap': 100, 'card': '1-1', 'pixels': 'pixelcopy', 'kind': 'pop', 'capture_to_ui_ms': 250}
        ])

    def test_parse_without_acceptance_is_not_an_ocr_pass(self):
        self.assertEqual(accepted_chains('\n'.join([
            'VexoLocalOcr: pixels src=pixelcopy cap=100 card=1-1',
            'VexoLocalOcr: parsed kind=pop cap=100 card=1-1',
            'VexoLocalOcr: dispatched kind=offer cap=100 card=1-1',
            'VexoLocalOcr: witness=late_discarded card=1-1 t=19415',
        ])), [])
