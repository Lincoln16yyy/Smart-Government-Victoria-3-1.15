"""Exercise the generated ranking and check its journal wiring."""
from __future__ import annotations

import json
import re
import unittest

from test_advisor_generation import ROOT, read

import build_research_data as compiler
from build_research_gui import section
from pdx_parse import parse


class Ranking:
    """Run only the generated effect subset with supplied country signals."""

    def __init__(self, contexts=(), researched=(), active=None):
        self.contexts = {f"sg_research_{name}" for name in contexts}
        self.researched = set(researched)
        self.active = active
        self.variables = {"sg_enabled": 1}
        self.effects = dict_blocks(compiler.EFFECTS)
        self.triggers = dict_blocks(compiler.TRIGGERS)

    def test(self, nodes):
        return all(self.condition(*node) for node in nodes)

    def condition(self, key, op, value):
        if key == "NOT":
            return not self.test(value)
        if key == "has_technology_researched":
            return value in self.researched
        if key == "is_researching_technology":
            return value == self.active
        if key == "has_variable":
            return value in self.variables
        if key == "is_player":
            return value == "yes"
        if key in self.triggers:
            return self.test(self.triggers[key])
        if key.startswith("var:") and op == ">":
            return self.number(key) > self.number(value)
        if key.removeprefix("sg_research_") in compiler.CONTEXTS:
            return key in self.contexts
        raise AssertionError(f"Unexpected trigger: {key} {op} {value}")

    def number(self, value):
        return self.variables[value[4:]] if value.startswith("var:") else int(value)

    def execute(self, nodes):
        matched = False
        for key, _, value in nodes:
            if key == "if":
                matched = False
            if key in {"if", "else_if"}:
                if not matched and self.test(value[0][2]):
                    matched = True
                    self.execute(value[1:])
            elif key == "set_variable":
                operands = {name: operand for name, _, operand in value}
                self.variables[operands["name"]] = self.number(operands["value"])
            elif key == "remove_variable":
                self.variables.pop(value, None)
            else:
                assert value == "yes" and key in self.effects, key
                self.execute(self.effects[key])

    def review(self):
        self.execute(self.effects["sg_research_rank"])
        return [NAMES[self.variables[f"sg_research_{slot}_id"]] for slot in compiler.SLOTS
                if self.variables.get(f"sg_research_{slot}_id")]


def dict_blocks(path):
    return {name: nodes for name, _, nodes in parse(read(path))}


RECORDS = json.loads(read(compiler.MANIFEST))
NAMES = {record["id"]: record["name"] for record in RECORDS}
REQUIREMENTS = {record["name"]: set(record["prerequisites"]) for record in RECORDS}


class TechnologyAdvisorTests(unittest.TestCase):
    def test_availability_requires_all_prerequisites_and_excludes_current_and_completed(self):
        rail = Ranking(contexts=["infrastructure"], researched={"mechanical_tools"})
        self.assertEqual(rail.review(), [])
        rail.researched.add("atmospheric_engine")
        self.assertEqual(rail.review(), ["railways"])
        rail.active = "railways"
        self.assertEqual(rail.review(), [])
        rail.active = None
        rail.researched.add("railways")
        self.assertEqual(rail.review(), [])

    def test_context_changes_first_choice_and_keeps_distinct_followups(self):
        researched = {"mechanical_tools", "atmospheric_engine", "napoleonic_warfare"}
        advisor = Ranking(contexts=["infrastructure", "literacy"], researched=researched)
        self.assertEqual(advisor.review(), ["railways", "rationalism"])
        advisor.contexts.add("sg_research_defense")
        self.assertEqual(advisor.review(), ["field_works", "railways", "rationalism"])
        advisor.researched.add("field_works")
        self.assertEqual(advisor.review(), ["railways", "rationalism"])
        self.assertEqual(advisor.review(), ["railways", "rationalism"])

    def test_rank_inserts_between_slots_and_discards_fourth_candidate(self):
        advisor = Ranking(
            contexts=["infrastructure", "literacy", "defense", "administration", "debt_pressure"],
            researched={"mechanical_tools", "atmospheric_engine", "napoleonic_warfare",
                        "centralization", "banking"},
        )
        self.assertEqual(advisor.review(), ["field_works", "central_banking", "central_archives"])

    def test_clear_removes_all_stored_state_and_disabled_review_does_nothing(self):
        advisor = Ranking(contexts=["literacy"])
        self.assertEqual(advisor.review(), ["rationalism"])
        del advisor.variables["sg_enabled"]
        advisor.execute(advisor.effects["sg_research_clear"])
        self.assertEqual(advisor.review(), [])
        self.assertEqual(advisor.variables, {})

    def test_generated_artifacts_match_policy_and_share_journal(self):
        self.assertEqual({t["category"] for t in RECORDS}, {"production", "military", "society"})
        self.assertTrue(all(t["can_research"] for t in RECORDS))
        self.assertNotIn("sericulture", REQUIREMENTS)
        for path, generate in ((compiler.EFFECTS, compiler.emit_effects),
                               (compiler.TRIGGERS, compiler.emit_triggers),
                               (compiler.SGUIS, compiler.emit_sguis)):
            self.assertEqual(read(path).split("\n", 1)[1], generate(RECORDS))
        contexts = dict_blocks("common/scripted_triggers/sg_research_context.txt")
        self.assertTrue(all(f"sg_research_{t['context']}" in contexts for t in RECORDS))
        widget = section()
        self.assertIn(widget, read("gui/journal_entry_widgets/sg_law_advisor.gui"))
        references = set(re.findall(r"GetScriptedGui\('(sg_research_\w+)'\)", widget))
        self.assertEqual(references, dict_blocks(compiler.SGUIS).keys())
        labels = set(re.findall(r'(?:text|tooltip) = "(sg_research_\w+)"', widget))
        for lang in ("english", "braz_por"):
            localization = read(f"localization/{lang}/sg_research_l_{lang}.yml")
            keys = set(re.findall(r"^ (sg_research_\w+):0", localization, re.M))
            self.assertTrue(labels <= keys)
            self.assertIn(".GetProgress(GetPlayer.Self)", localization)

    def test_research_lifecycle_only_refreshes_recommendations(self):
        events = dict_blocks("common/on_actions/sg_research_on_actions.txt")
        for event in ("on_acquired_technology", "on_research_technology_started"):
            self.assertEqual(events[event], [("on_actions", "=", [("sg_research_update", None, None)])])
        self.assertIn("sg_research_update", read("common/on_actions/sg_on_actions.txt"))
        lifecycle = dict_blocks("common/scripted_effects/sg_effects.txt")
        self.assertIn(("sg_research_rank", "=", "yes"), lifecycle["sg_initialize_country"])
        self.assertIn(("sg_research_clear", "=", "yes"), lifecycle["sg_disable_country"])
        forbidden = r"\b(post_notification|add_technology|start_research|set_technology_progress)\s*="
        self.assertNotRegex(read(compiler.EFFECTS), forbidden)
