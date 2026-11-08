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

    def test_legitimacy_risk_uses_its_specific_theme(self) -> None:
        self.assertEqual(
            build_law_data.choose_risk_theme(
                "lawgroup_power_structure",
                [
                    {
                        "key": "country_legitimacy_ideological_incoherence_mult",
                        "risk": 10.0,
                    }
                ],
            ),
            8,
        )
        law = next(item for item in LAWS if item["id"] == "law_autocracy")
        self.assertEqual(law["risk_theme"], 8)


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
            for field in ("benefit", "risk", "politics", "enactment_chance", "score")
        ]
        actual_values = definition_names(
            self.values, r"^(sg_law_(?:benefit|risk|politics|score)_[A-Za-z0-9_]+)\s*="
        )
        actual_values += definition_names(
            self.values, r"^(sg_law_enactment_chance_[A-Za-z0-9_]+)\s*="
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
        merit = extract_block(self.values, "sg_law_merit_law_no_schools")
        self.assertIn("add = { value = sg_law_benefit_law_no_schools }", merit)
        self.assertIn("add = { value = sg_law_politics_law_no_schools }", merit)
        self.assertIn(
            "subtract = { value = sg_law_risk_law_no_schools multiply = 0.5 }",
            merit,
        )
        block = extract_block(self.values, "sg_law_score_law_no_schools")
        self.assertIn("add = { value = sg_law_merit_law_no_schools }", block)
        politics = extract_block(self.values, "sg_law_politics_law_no_schools")
        self.assertIn("law_stance = { law = law_type:law_no_schools", politics)
        self.assertIn(
            "law_enactment_stance = { law = law_type:law_no_schools",
            politics,
        )
        self.assertIn(
            "add = { value = sg_law_enactment_chance_law_no_schools multiply = 0.5 }",
            block,
        )

    def test_every_group_compares_against_its_current_law(self) -> None:
        by_group: dict[str, set[str]] = {}
        for law in LAWS:
            by_group.setdefault(law["group"], set()).add(law["id"])
        self.assertEqual(len(by_group), 26)
        for group, laws_in_group in by_group.items():
            block = extract_block(self.values, f"sg_law_current_merit_{group}")
            for law_id in laws_in_group:
                self.assertIn(f"has_law = law_type:{law_id}", block)
                self.assertIn(f"add = {{ value = sg_law_merit_{law_id} }}", block)
            floor = extract_block(self.values, f"sg_law_upgrade_floor_{group}")
            self.assertIn(f"value = sg_law_current_merit_{group}", floor)
            self.assertIn(
                f"add = {build_law_data.MIN_IMPROVEMENT}", floor
            )

    def test_ranking_gates_each_law_on_real_improvement(self) -> None:
        self.assertNotIn("sg_law_group_leader", self.rank)
        self.assertNotIn("sg_law_candidate", self.rank)
        for law in LAWS:
            self.assertIn(
                f"sg_law_merit_{law['id']} >= "
                f"sg_law_upgrade_floor_{law['group']}",
                self.rank,
            )
        self.assertIn(
            "set_variable = { name = sg_last_rank_upgrade_filtered value = 0 }",
            self.rank,
        )
        self.assertEqual(
            self.rank.count(
                "change_variable = { name = sg_last_rank_upgrade_filtered add = 1 }"
            ),
            len(LAWS),
        )

    def test_generated_values_use_valid_interest_group_and_fraction_syntax(self) -> None:
        self.assertNotIn("scope_interest_group", self.values)
        self.assertNotIn("radical_fraction >", self.values)
        self.assertIn("every_interest_group = {", self.values)
        self.assertIn("any_interest_group = {", self.values)
        self.assertIn("radical_fraction = { value >=", self.values)

    def test_powerful_interest_group_opposition_penalizes_risk(self) -> None:
        sample = extract_block(self.values, "sg_law_powerful_opposition_law_monarchy")
        self.assertIn("is_powerful = yes", sample)
        self.assertIn("strongly_disapprove", sample)
        risk = extract_block(self.values, "sg_law_risk_law_monarchy")
        self.assertIn("sg_law_powerful_opposition_law_monarchy > 0", risk)
        self.assertIn("add = 12", risk)
        for slot in (1, 2, 3):
            self.assertIn(
                f"set_variable = {{ name = sg_top_{slot}_opposition value = "
                "sg_law_powerful_opposition_",
                self.rank,
            )

    def test_availability_matches_runtime_promulgation_constraints(self) -> None:
        for law_id in (
            "law_hindu_caste_enforced",
            "law_hindu_caste_codified",
            "law_national_supremacy",
        ):
            block = extract_block(self.availability, f"sg_law_available_{law_id}")
            self.assertIn("NOT = { enacting_any_law = yes }", block)
            self.assertIn(
                f'"enactment_chance_for_law(law_type:{law_id})" >= '
                "define:NPolitics|LAW_MIN_SUCCESS_CHANCE",
                block,
            )
            self.assertNotIn("define:LAW_MIN_SUCCESS_CHANCE", block)

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
            self.assertIn(f"sg_top_{slot}_enactment_chance", self.rank)
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
        self.sguis = read("common/scripted_guis/sg_law_sguis.txt")
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
            "sg_last_rank_upgrade_filtered",
            "sg_last_rank_eligible",
            "sg_last_ranked_count",
            "sg_ignored_1",
            "sg_ignored_2",
            "sg_ignored_3",
        ):
            self.assertIn(f"remove_variable = {variable}", body)
        self.assertIn("sg_clear_rank = yes", body)
        for slot in (1, 2, 3):
            self.assertIn(
                f"remove_variable = sg_top_{slot}_enactment_chance",
                self.effects,
            )
            self.assertIn(
                f"remove_variable = sg_top_{slot}_opposition",
                self.effects,
            )
        self.assertNotIn("remove_variable = sg_schema_version", body)

    def test_empty_state_and_explanations_are_rendered(self) -> None:
        self.assertIn("text = \"sg_empty\"", self.gui)
        self.assertIn("sg_top_1_visible_sgui", self.gui)
        for slot in (1, 2, 3):
            self.assertIn(f"text = \"sg_why_ranked_{slot}\"", self.gui)
            self.assertIn(f"sg_top_{slot}_benefit_score", self.english)
            self.assertIn(f"sg_top_{slot}_politics", self.english)
            self.assertIn(f"sg_top_{slot}_risk_score", self.english)
            self.assertIn(f"sg_top_{slot}_enactment_chance", self.english)
        self.assertIn("benefit + government support", self.english)
        self.assertIn("ranked globally", self.english)
        self.assertIn("already in force", self.english)
        self.assertIn("sg_last_rank_upgrade_filtered", self.english)
        portuguese = read("localization/braz_por/sg_l_braz_por.yml")
        self.assertIn("metade de", portuguese)
        self.assertIn("já estão em vigor", portuguese)
        self.assertIn("sg_last_rank_upgrade_filtered", portuguese)

    def test_dynamic_gui_expressions_use_raw_text_and_known_formats(self) -> None:
        self.assertNotRegex(
            self.gui,
            r'(?m)^\s*text = "\[(?:SelectLocalization|JournalEntry\.)',
        )
        self.assertNotIn('default_format = "#P"', self.gui)
        self.assertIn('default_format = "#positive_value"', self.gui)
        self.assertIn("raw_text = \"[JournalEntry.GetCountry", self.gui)
        self.assertNotIn("EqualTo_int32(", self.gui)
        self.assertIn("_law_law_mass_conscription_visible_sgui", self.gui)
        self.assertIn("minimumsize = { 500 190 }", self.gui)
        self.assertIn("size = { 115 34 }", self.gui)
        self.assertIn("size = { 116 30 }", self.gui)
        self.assertIn('text = "sg_focus_1"', self.gui)

    def test_enactment_pause_and_opposition_warning_are_rendered(self) -> None:
        handwritten_sguis = read("common/scripted_guis/sg_scripted_guis.txt")
        self.assertIn('text = "sg_enacting"', self.gui)
        self.assertIn("sg_enacting_visible_sgui", self.gui)
        self.assertIn("sg_enacting_visible_sgui = {", handwritten_sguis)
        self.assertIn('text = "sg_opposition_warning"', self.gui)
        for slot in (1, 2, 3):
            self.assertIn(f"sg_top_{slot}_opposition_visible_sgui", self.gui)
            self.assertIn(
                f"sg_top_{slot}_opposition_visible_sgui = {{", handwritten_sguis
            )
        self.assertIn("sg_enacting:0", self.english)
        self.assertIn("sg_opposition_warning:0", self.english)
        portuguese = read("localization/braz_por/sg_l_braz_por.yml")
        self.assertIn("sg_enacting:0", portuguese)
        self.assertIn("sg_opposition_warning:0", portuguese)

    def test_gui_does_not_use_invalid_hasvariable_function(self) -> None:
        self.assertNotIn("HasVariable(", self.gui)
        self.assertIn(
            "GetScriptedGui('sg_rank_diagnostic_visible_sgui')", self.gui
        )
        self.assertIn(
            "sg_rank_diagnostic_visible_sgui = {",
            read("common/scripted_guis/sg_scripted_guis.txt"),
        )

    def test_all_game_text_files_use_utf8_bom(self) -> None:
        patterns = ("localization/**/*.yml", "common/**/*.txt", "gui/**/*.gui")
        for pattern in patterns:
            for path in ROOT.glob(pattern):
                self.assertTrue(
                    path.read_bytes().startswith(b"\xef\xbb\xbf"),
                    str(path.relative_to(ROOT)),
                )


    def test_gui_does_not_set_autoresize_on_plain_widgets(self) -> None:
        lines = self.gui.splitlines()
        offenders: list[int] = []
        for index, line in enumerate(lines):
            if not re.match(r"^\s*widget\s*=\s*\{\s*$", line):
                continue
            indent = len(line) - len(line.lstrip("\t"))
            for child_index in range(index + 1, min(index + 8, len(lines))):
                child = lines[child_index]
                if not child.strip():
                    continue
                child_indent = len(child) - len(child.lstrip("\t"))
                if child_indent <= indent:
                    break
                if child_indent == indent + 1 and child.strip() == "autoresize = yes":
                    offenders.append(child_index + 1)
                    break
        self.assertEqual(offenders, [])
        # The property is valid on textboxes and must stay there.
        self.assertIn("autoresize = yes", self.gui)

    def test_each_slot_law_branch_uses_its_matching_visibility_sgui(self) -> None:
        for slot in (1, 2, 3):
            for law in LAWS:
                marker = (
                    f"GetScriptedGui('sg_top_{slot}_law_{law['id']}_visible_sgui')"
                )
                self.assertEqual(self.gui.count(marker), 3, marker)
                sgui = (
                    f"sg_top_{slot}_law_{law['id']}_visible_sgui = {{"
                )
                self.assertIn(sgui, self.sguis)
                self.assertIn(
                    f"var:sg_top_{slot}_id = {law['sid']}",
                    self.sguis,
                )

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

    def test_ignored_laws_management_and_individual_restore_sguis(self) -> None:
        for slot in (1, 2, 3):
            self.assertIn(f"sg_restore_ignored_{slot} = {{", self.effects)
            self.assertIn(f"sg_restore_ignored_{slot}_sgui = {{", read("common/scripted_guis/sg_scripted_guis.txt"))
            for law in LAWS:
                marker = f"GetScriptedGui('sg_ignored_{slot}_law_{law['id']}_visible_sgui')"
                self.assertEqual(self.gui.count(marker), 1, marker)
                sgui = f"sg_ignored_{slot}_law_{law['id']}_visible_sgui = {{"
                self.assertIn(sgui, self.sguis)
        self.assertIn("text = \"sg_ignored_title\"", self.gui)
        self.assertIn("text = \"sg_restore\"", self.gui)
        self.assertIn("sg_restore:0", self.english)
        self.assertIn("sg_restore:0", read("localization/braz_por/sg_l_braz_por.yml"))


if __name__ == "__main__":
    unittest.main()
