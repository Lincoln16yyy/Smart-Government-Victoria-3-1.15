import tempfile
import unittest
from pathlib import Path

from tools import bpm_government


class BetterPoliticsLawDatabaseTest(unittest.TestCase):
    def test_merges_prerequisites_and_keeps_latest_modifier_value(self):
        merged = bpm_government.inject(
            'group = lawgroup_test can_enact = { exists = ruler } '
            'disallowing_laws = { law_a } modifier = { a = 1 b = 2 }',
            'can_enact = { legitimacy > 50 } disallowing_laws = { law_b } modifier = { b = 4 }',
        )
        fields = {key: value for key, _, value in bpm_government.fields(merged)}
        self.assertEqual(fields['can_enact'], '{ exists = ruler legitimacy > 50 }')
        self.assertEqual(fields['disallowing_laws'], '{ law_a law_b }')
        self.assertEqual(fields['modifier'], '{ a = 1 b = 4 }')
        self.assertEqual(fields['group'], 'lawgroup_test')

    def test_replacement_discards_old_law_and_direct_file_overwrite_applies(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game = root / 'game'
            bpm = root / 'bpm'
            for source in (game, bpm):
                (source / 'common/laws').mkdir(parents=True)
            (game / 'common/laws/00_base.txt').write_text(
                'law_a = { group = lawgroup_a } law_b = { group = lawgroup_b }')
            (game / 'common/laws/01_both.txt').write_text('law_overwritten = { }')
            (bpm / 'common/laws/01_both.txt').write_text('law_new = { group = lawgroup_b }')
            (bpm / 'common/laws/02_patch.txt').write_text(
                'REPLACE:law_a = { group = lawgroup_c } '
                'INJECT:law_b = { can_enact = { custom_tooltip = "two words" } }')
            bpm_government.make_database(game, bpm, root / 'out')
            database = (root / 'out/common/laws/sg_bpm_inputs.txt').read_text(encoding='utf-8-sig')
            self.assertNotIn('lawgroup_a', database)
            self.assertNotIn('law_overwritten', database)
            self.assertIn('law_new', database)
            self.assertIn('lawgroup_c', database)
            self.assertIn('custom_tooltip = "two words"', database)
