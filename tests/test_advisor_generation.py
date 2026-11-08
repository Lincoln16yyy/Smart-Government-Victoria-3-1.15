#!/usr/bin/env python3
"""Regression tests for the generated Smart Government Advisor artifacts."""
from __future__ import annotations

import json
import re
import sys
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import build_law_data  # noqa: E402


DATA = json.loads((ROOT / "data" / "law_data.json").read_text(encoding="utf-8"))
LAW_IDS = json.loads((ROOT / "data" / "law_ids.json").read_text(encoding="utf-8"))
COMPATIBILITY_IDS = json.loads(
    (ROOT / "tests" / "fixtures" / "law_ids_compatibility.json").read_text(encoding="utf-8")
)
LAWS = DATA["laws"]


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8-sig")


def definition_names(text: str, pattern: str) -> list[str]:
    return re.findall(pattern, text, re.MULTILINE)


def extract_block(text: str, name: str) -> str:
    match = re.search(rf"(?m)^{re.escape(name)}\s*=\s*\{{", text)
    if match is None:
        raise AssertionError(f"missing block: {name}")
    close = build_law_data.find_matching_brace(text, text.find("{", match.start()))
    return text[match.end() : close]


class GeneratedDataTests(unittest.TestCase):
    def test_real_law_inventory_and_stable_ids(self) -> None:
        self.assertEqual(len(LAWS), 148)
        self.assertEqual(len({law["id"] for law in LAWS}), len(LAWS))
        self.assertEqual(len({law["sid"] for law in LAWS}), len(LAWS))
        self.assertTrue(set(law["id"] for law in LAWS) <= set(LAW_IDS))
        for law in LAWS:
            self.assertEqual(LAW_IDS[law["id"]], law["sid"])
            self.assertEqual(COMPATIBILITY_IDS[law["id"]], law["sid"])
            self.assertGreater(law["sid"], 0)
        self.assertEqual(
            set(COMPATIBILITY_IDS) - set(LAWS[i]["id"] for i in range(len(LAWS))),
            set(LAW_IDS) - set(law["id"] for law in LAWS),
        )

    def test_modifier_scoring_is_deterministic_and_ignores_unmapped_effects(self) -> None:
        benefit, risk, annotated = build_law_data.score_modifiers(
            [
                ("state_education_access_add", "0.10"),
                ("state_radicals_from_political_movements_mult", "0.20"),
                ("unmapped_modifier", "100"),
            ]
        )
        self.assertEqual(benefit, 6.0)
        self.assertEqual(risk, 8.0)
        self.assertEqual(len(annotated), 3)
        self.assertEqual(annotated[-1]["benefit"], 0.0)
        self.assertEqual(annotated[-1]["risk"], 0.0)

    def test_neutral_theme_requires_no_positive_benefit_signal(self) -> None:
        self.assertEqual(
            build_law_data.choose_benefit_theme(
                [{"key": "state_education_access_add", "benefit": 0.0}]
            ),
            build_law_data.BENEFIT_NEUTRAL_THEME,
        )


class GeneratedScriptTests(unittest.TestCase):
    def setUp(self) -> None:
        self.availability = read("common/scripted_triggers/sg_law_availability.txt")
        self.values = read("common/script_values/sg_law_scores.txt")
        self.rank = read("common/scripted_effects/sg_law_rank.txt")
        self.actions = read("common/scripted_effects/sg_law_actions.txt")
        self.sguis = read("common/scripted_guis/sg_law_sguis.txt")

    def test_generated_files_have_one_consistent_block_per_law(self) -> None:
        ids = {law["id"] for law in LAWS}
        expected_availability = [f"sg_law_available_{law_id}" for law_id in sorted(ids)]
        actual_availability = definition_names(
            self.availability, r"^(sg_law_available_[A-Za-z0-9_]+)\s*="
        )
        self.assertEqual(Counter(actual_availability), Counter(expected_availability))

        expected_values = [
            f"sg_law_{field}_{law_id}"
            for law_id in sorted(ids)
            for field in ("benefit", "risk", "politics", "score")
        ]
        actual_values = definition_names(
            self.values, r"^(sg_law_(?:benefit|risk|politics|score)_[A-Za-z0-9_]+)\s*="
        )
        self.assertEqual(Counter(actual_values), Counter(expected_values))

        expected_actions = [
            f"sg_{action}_law_{law_id}"
            for law_id in sorted(ids)
            for action in ("enact", "ignore")
        ]
        actual_actions = definition_names(
            self.actions, r"^(sg_(?:enact|ignore)_law_[A-Za-z0-9_]+)\s*="
        )
        self.assertEqual(Counter(actual_actions), Counter(expected_actions))

        expected_sguis = [
            f"sg_{action}_law_{law_id}_sgui"
            for law_id in sorted(ids)
            for action in ("enact", "ignore")
        ]
        actual_sguis = definition_names(
            self.sguis, r"^(sg_(?:enact|ignore)_law_[A-Za-z0-9_]+_sgui)\s*="
        )
        self.assertEqual(Counter(actual_sguis), Counter(expected_sguis))

    def test_ranking_contains_one_evaluation_block_for_every_law(self) -> None:
        ids = {law["id"] for law in LAWS}
        for law_id in ids:
            marker = f"\t\t\tsg_law_available_{law_id} = yes"
            self.assertEqual(self.rank.count(marker), 1, law_id)

    def test_score_formula_and_politics_are_wired_into_generated_values(self) -> None:
        block = extract_block(self.values, "sg_law_score_law_no_schools")
        self.assertIn("add = { value = sg_law_benefit_law_no_schools }", block)
        self.assertIn("add = { value = sg_law_politics_law_no_schools }", block)
        self.assertIn(
            "subtract = { value = sg_law_risk_law_no_schools multiply = 0.5 }",
            block,
        )
        politics = extract_block(self.values, "sg_law_politics_law_no_schools")
        self.assertIn("law_stance = { law = law_type:law_no_schools", politics)
        self.assertIn(
            "law_enactment_stance = { law = law_type:law_no_schools",
            politics,
        )

    def test_ranking_initializes_sentinel_slots_and_tracks_counts(self) -> None:
        self.assertIn("set_variable = { name = sg_top_1_id value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_top_2_id value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_top_3_id value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_last_rank_evaluated value = 148 }", self.rank)
        self.assertIn("set_variable = { name = sg_last_rank_available value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_last_rank_ignored value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_last_rank_eligible value = 0 }", self.rank)
        self.assertIn("set_variable = { name = sg_last_ranked_count value = 0 }", self.rank)
        self.assertIn("var:sg_top_1_id > 0", self.rank)
        self.assertEqual(
            self.rank.count(
                "change_variable = { name = sg_last_ranked_count add = 1 }"
            ),
            3,
        )
        for slot in (1, 2, 3):
            self.assertIn(f"var:sg_top_{slot}_id > 0", self.rank)

    def test_actions_recheck_and_rerank(self) -> None:
        law = LAWS[0]["id"]
        block = extract_block(self.actions, f"sg_enact_law_{law}")
        guard_end = block.find("\n\t}\n")
        rerank = block.find("\n\tsg_rank_laws = yes")
        self.assertGreaterEqual(guard_end, 0)
        self.assertGreater(rerank, guard_end)
        self.assertIn(f"sg_law_available_{law} = yes", block)
        self.assertIn("NOT = { enacting_any_law = yes }", block)
        self.assertIn(f"start_enactment = law_type:{law}", block)


class RuntimeSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.effects = read("common/scripted_effects/sg_effects.txt")
        self.journal = read("common/journal_entries/sg_journal_entries.txt")
        self.gui = read("gui/journal_entry_widgets/sg_law_advisor.gui")
        self.english = read("localization/english/sg_l_english.yml")
        self.generated_english = read("localization/english/sg_generated_l_english.yml")
        self.generated_portuguese = read("localization/braz_por/sg_generated_l_braz_por.yml")

    def test_refresh_date_is_written_by_ranking_and_initialized_for_old_saves(self) -> None:
        self.assertIn("set_variable = { name = sg_last_refresh_year value = year }", self.gui_or_rank())
        self.assertIn("set_variable = { name = sg_last_refresh_month value = month }", self.gui_or_rank())
        self.assertIn("sg_initialize_refresh_date = yes", self.effects)
        self.assertIn("sg_rank_laws = yes", self.effects)

    def gui_or_rank(self) -> str:
        return read("common/scripted_effects/sg_law_rank.txt")

    def test_disable_cleans_runtime_state_but_preserves_schema(self) -> None:
        disable = re.search(r"sg_disable_country\s*=\s*\{(.*?)\n\}", self.effects, re.DOTALL)
        self.assertIsNotNone(disable)
        assert disable is not None
        body = disable.group(1)
        for variable in (
            "sg_enabled",
            "sg_last_refresh_year",
            "sg_last_refresh_month",
            "sg_last_rank_evaluated",
            "sg_last_rank_available",
            "sg_last_rank_ignored",
            "sg_last_rank_eligible",
            "sg_last_ranked_count",
            "sg_ignored_1",
            "sg_ignored_2",
            "sg_ignored_3",
        ):
            self.assertIn(f"remove_variable = {variable}", body)
        self.assertIn("sg_clear_rank = yes", body)
        self.assertNotIn("remove_variable = sg_schema_version", body)

    def test_empty_state_and_explanations_are_rendered(self) -> None:
        self.assertIn("text = \"sg_empty\"", self.gui)
        self.assertIn("sg_top_1_visible_sgui", self.gui)
        for slot in (1, 2, 3):
            self.assertIn(f"text = \"sg_why_ranked_{slot}\"", self.gui)
            self.assertIn(f"sg_top_{slot}_benefit_score", self.english)
            self.assertIn(f"sg_top_{slot}_politics", self.english)
            self.assertIn(f"sg_top_{slot}_risk_score", self.english)
        self.assertIn("benefit + government support", self.english)
        self.assertIn("metade de", read("localization/braz_por/sg_l_braz_por.yml"))

    def test_dynamic_gui_expressions_use_raw_text_and_known_formats(self) -> None:
        self.assertNotRegex(
            self.gui,
            r'(?m)^\s*text = "\[(?:SelectLocalization|JournalEntry\.)',
        )
        self.assertNotIn('default_format = "#P"', self.gui)
        self.assertIn('default_format = "#positive_value"', self.gui)
        self.assertIn("raw_text = \"[SelectLocalization(", self.gui)
        self.assertIn("raw_text = \"[JournalEntry.GetCountry", self.gui)

    def test_every_law_has_bilingual_generated_explanations_and_tooltip_keys(self) -> None:
        for law in LAWS:
            sid = law["sid"]
            for text in (self.generated_english, self.generated_portuguese):
                self.assertRegex(text, rf"(?m)^\s*sg_law_name_{sid}:")
                self.assertRegex(text, rf"(?m)^\s*sg_law_group_{sid}:")
                self.assertRegex(text, rf"(?m)^\s*sg_law_tip_{sid}:")
                self.assertRegex(text, rf"(?m)^\s*sg_law_benefit_{re.escape(law['id'])}:")
                self.assertRegex(text, rf"(?m)^\s*sg_law_risk_{re.escape(law['id'])}:")

    def test_generated_law_data_has_the_fields_consumed_by_rank_and_gui(self) -> None:
        required = {
            "id",
            "sid",
            "benefit",
            "risk",
            "benefit_theme",
            "risk_theme",
            "focus",
        }
        for law in LAWS:
            self.assertTrue(required <= law.keys())


if __name__ == "__main__":
    unittest.main()
