"""Targeted checks for military policy and its journal integration."""
from __future__ import annotations

import operator
import re
import unittest

from test_advisor_generation import ROOT, read
from build_gui import military_section
from pdx_parse import Parser


def blocks(path):
    return {key: children for key, _, children in Parser(read(path)).parse()}


def child(nodes, key):
    return next(value for name, _, value in nodes if name == key)


class MilitaryAdvisorTests(unittest.TestCase):
    def setUp(self):
        self.triggers = blocks("common/scripted_triggers/sg_military_triggers.txt")
        self.effects = blocks("common/scripted_effects/sg_military_effects.txt")
        self.sguis = blocks("common/scripted_guis/sg_military_sguis.txt")

    def test_fiscal_guard_matches_observed_balance_and_reserves(self):
        def number(expression, readings):
            if isinstance(expression, list):
                result = 0
                for field, _, value in expression:
                    amount = number(value, readings)
                    if field == "value":
                        result = amount
                    elif field == "subtract":
                        result -= amount
                    elif field == "multiply":
                        result *= amount
                    elif field == "min":
                        result = max(result, amount)
                    else:
                        self.fail(f"Unexpected fiscal arithmetic: {field}")
                return result
            if expression == "no":
                return False
            if expression in readings:
                return readings[expression]
            return float(expression)

        comparators = {">": operator.gt, ">=": operator.ge, "<=": operator.le, "=": operator.eq}
        base = dict(net_total_income=100, net_fixed_income=80, fixed_income=180,
                    gold_reserves=1200, principal=0, military_expenses=200, in_default=False)
        for changes, expected in [
            ({}, True),
            ({"gold_reserves": 1199}, False),
            ({"net_total_income": 99}, False),
            ({"net_total_income": -1}, False),
            ({"net_fixed_income": -1}, False),
            ({"principal": 1}, False),
            ({"in_default": True}, False),
        ]:
            with self.subTest(changes=changes):
                readings = base | changes
                result = all(comparators[op](readings[key], number(value, readings))
                             for key, op, value in self.triggers["sg_military_can_spend"])
                self.assertEqual(result, expected)

    def test_expansion_yields_to_shortage_fiscal_and_conflict_guards(self):
        review = child(self.effects["sg_military_review"], "if")
        branches = [body for key, _, body in review if key in ("if", "else_if")]
        self.assertEqual([child(branch, "limit")[0][0] for branch in branches[:3]], [
            "sg_military_supply_shortage", "sg_military_can_spend", "sg_military_at_risk",
        ])
        for kind in ("land", "naval"):
            with self.subTest(kind=kind):
                self.assertTrue(any(
                    (f"sg_military_open_{kind}_plan", "=", "yes") in branch
                    and ("NOT", "=", [("has_variable", "=", f"sg_military_{kind}_cooldown")])
                    in child(branch, "limit")
                    for branch in branches[3:]
                ))
                eligibility = self.triggers[f"sg_military_{kind}_eligible"]
                self.assertIn(("sg_military_can_spend", "=", "yes"), eligibility)
                self.assertIn(("sg_military_at_risk", "=", "no"), eligibility)

    def test_recruitment_requires_typed_progress_in_the_selected_formation(self):
        for kind, value in (("land", "sg_military_line_count"),
                            ("naval", "sg_military_frigate_count")):
            with self.subTest(kind=kind):
                plan = child(self.effects[f"sg_military_review_{kind}_plan"], "if")
                success = child(plan, "if")
                formation = child(child(success, "limit"), f"var:sg_military_{kind}_formation")
                self.assertIn(("owner", "=", "scope:sg_military_country"), formation)
                goal = "land_formation_goal" if kind == "land" else "naval_goal"
                self.assertIn((value, ">=", f"scope:sg_military_country.var:sg_military_{goal}"), formation)
                if kind == "land":
                    self.assertIn(("army_size", ">=", "var:sg_military_land_goal"), child(success, "limit"))
                self.assertEqual(child(child(success, "set_variable"), "value"), "1")
                self.assertIn((f"sg_military_close_{kind}_plan", "=", "yes"), child(plan, "else_if"))
                close = self.effects[f"sg_military_close_{kind}_plan"]
                self.assertEqual(child(child(close, "set_variable"), "days"), "90")

    def test_disable_removes_every_military_variable(self):
        written = set()
        for path in (ROOT / "common").rglob("sg_military_*.txt"):
            written.update(re.findall(r"name = (sg_military_\w+)", path.read_text(encoding="utf-8-sig")))
        cleanup = self.effects["sg_military_clear"] + self.effects["sg_military_close_land_plan"]
        cleanup += self.effects["sg_military_close_naval_plan"]
        removed = {value for key, _, value in cleanup if key == "remove_variable"}
        self.assertEqual(written, removed)
        lifecycle = blocks("common/scripted_effects/sg_effects.txt")
        self.assertIn(("sg_military_clear", "=", "yes"), lifecycle["sg_disable_country"])
        for event in ("sg_initialize_country", "sg_monthly_update"):
            self.assertIn("sg_military_review", repr(lifecycle[event]))

    def test_journal_widget_is_generated_and_localized_in_both_languages(self):
        section = military_section()
        self.assertIn(section, read("gui/journal_entry_widgets/sg_law_advisor.gui"))
        references = set(re.findall(r"GetScriptedGui\('(sg_military_\w+)'\)", section))
        self.assertEqual(references, self.sguis.keys())
        labels = set(re.findall(r'(?:text|tooltip) = "(sg_military_\w+)"', section))
        for language in ("braz_por", "english"):
            path = ROOT / f"localization/{language}/sg_military_l_{language}.yml"
            self.assertTrue(path.read_bytes().startswith(b"\xef\xbb\xbf"))
            localized = set(re.findall(r"^\s*(sg_military_\w+):0 ", read(path), re.M))
            self.assertEqual(labels, localized)
        ids = [child(child(gui, "is_shown"), "var:sg_military_card")
               for name, gui in self.sguis.items()
               if name.endswith("_sgui") and "var:sg_military_card" in repr(gui)]
        self.assertEqual(set(ids), set(map(str, range(10))))
        self.assertEqual(len(ids), 10)


if __name__ == "__main__":
    unittest.main()
