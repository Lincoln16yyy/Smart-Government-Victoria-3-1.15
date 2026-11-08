#!/usr/bin/env python3
"""Generate the Smart Government Advisor's law data from Victoria 3 files.

Reads every vanilla law and law group, extracts the real availability
requirements and modifier blocks, scores each law, and writes the generated
script triggers / script values / scripted effects / localization plus a JSON
snapshot for validation and documentation.

Usage:
    python3 tools/build_law_data.py
    python3 tools/build_law_data.py --game "/path/to/Victoria 3/game" --out .
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdx_parse import parse, strip_comments  # noqa: E402

DEFAULT_GAME = Path("/home/lincoln-ii/Games/Victoria 3/game")

# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    i = open_index
    while i < len(text):
        ch = text[i]
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
        else:
            if ch == '"':
                in_string = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise ValueError(f"unbalanced braces at {open_index}")


BLOCK_RE = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{")


def top_level_blocks(text: str):
    text = strip_comments(text)
    pos = 0
    while True:
        match = BLOCK_RE.search(text, pos)
        if not match:
            return
        open_index = text.find("{", match.start())
        close_index = find_matching_brace(text, open_index)
        yield match.group(1), text[open_index + 1 : close_index]
        pos = close_index + 1


def field_block(body: str, field: str) -> str | None:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*\{{", body)
    if not match:
        return None
    open_index = body.find("{", match.start())
    close_index = find_matching_brace(body, open_index)
    return body[open_index + 1 : close_index]


def field_scalar(body: str, field: str) -> str | None:
    match = re.search(rf"\b{re.escape(field)}\s*=\s*([^\s#}}]+)", body)
    return match.group(1) if match else None


def list_values(body: str, field: str) -> list[str]:
    raw = field_block(body, field)
    if raw is None:
        return []
    raw = strip_comments(raw)
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", raw)


def flat_pairs(raw: str | None) -> list[tuple[str, str]]:
    if not raw:
        return []
    result: list[tuple[str, str]] = []
    for key, _op, value in parse(raw):
        if isinstance(value, list):
            continue
        if value is None:
            continue
        result.append((key, value))
    return result


def numeric(value) -> float:
    if value is None:
        return 0.0
    text = str(value).strip().lower()
    if text in ("yes", "true"):
        return 1.0
    if text in ("no", "false"):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

# (regex, weight). The first matching rule wins. Benefit is 45 + sum; each
# contribution is clamped so one exotic modifier cannot dominate.
BENEFIT_RULES: list[tuple[str, float]] = [
    (r"country_authority_add$", 0.05),
    (r"country_authority_mult$", 15.0),
    (r"country_legitimacy_base_add$", 0.4),
    (r"country_legitimacy_govt_size_add$", 0.3),
    (r"country_legitimacy_govt_total_clout_add$", 0.3),
    (r"country_legitimacy_govt_total_votes_add$", 0.2),
    (r"country_legitimacy_headofstate_add$", 0.2),
    (r"country_legitimacy_ideological_incoherence_mult$", -30.0),
    (r"country_influence_mult$", 10.0),
    (r"country_tech_research_speed_mult$", 20.0),
    (r"country_production_tech_research_speed_mult$", 15.0),
    (r"country_tech_spread_mult$", 15.0),
    (r"country_production_tech_spread_mult$", 10.0),
    (r"state_tax_capacity_mult$", 30.0),
    (r"state_bureaucracy_population_base_cost_factor_mult$", -30.0),
    (r"country_bureaucracy_investment_cost_factor_mult$", -20.0),
    (r"country_institution_.*_max_investment_add$", 8.0),
    (r"country_institution_cost_.*_mult$", -15.0),
    (r"state_education_access_add$", 60.0),
    (r"state_peasants_education_access_add$", 50.0),
    (r"state_pop_qualifications_mult$", 15.0),
    (r".*qualification_growth.*$", 5.0),
    (r".*education_access_mult$", 8.0),
    (r".*cultural_acceptance_mult$", 6.0),
    (r"state_.*_mortality_mult$", -60.0),
    (r"state_.*_standard_of_living_add$", 25.0),
    (r"state_.*_expected_sol_(add|mult)$", 12.0),
    (r"state_birth_rate_mult$", 20.0),
    (r"state_working_adult_ratio_add$", 25.0),
    (r"state_dependent_wage_mult$", 8.0),
    (r"state_dependent_political_participation_add$", 5.0),
    (r"building_group_.*_throughput_add$", 60.0),
    (r"building_unincorporated_subsistence_output_mult$", 20.0),
    (r"building_minimum_incorporated_subsistence_employment_add$", 5.0),
    (r"state_minimum_incorporated_subsistence_arable_land_add$", 5.0),
    (r"building_self_investment_chance_add$", 15.0),
    (r"building_training_rate_mult$", 8.0),
    (r"building_nationalization_investment_return_add$", 15.0),
    (r"building_nationalization_cost_mult$", -10.0),
    (r"building_company_.*_dividends_add$", 10.0),
    (r"country_government_dividends_.*$", 10.0),
    (r"country_private_construction_allocation_mult$", 10.0),
    (r"country_loan_interest_rate_mult$", -25.0),
    (r"country_military_goods_cost_mult$", -20.0),
    (r"country_navy_goods_cost_mult$", -20.0),
    (r"country_government_wages_mult$", -15.0),
    (r"country_consumption_tax_cost_mult$", -15.0),
    (r"state_tariff_.*_add$", 10.0),
    (r"state_subvention_.*_add$", 4.0),
    (r"state_trade_.*_mult$", 8.0),
    (r"state_(import|export)_advantage_mult$", 8.0),
    (r"state_market_access_price_impact$", -20.0),
    (r"state_assimilation_mult$", 8.0),
    (r"state_conversion_mult$", 5.0),
    (r"state_migration_pull_unincorporated_mult$", 8.0),
    (r"country_migration_restrictiveness_add$", -15.0),
    (r"country_free_charters_add$", 6.0),
    (r"country_max_companies_add$", 6.0),
    (r"state_conscription_rate_(add|mult)$", 8.0),
    (r"state_building_(barrack|conscription_center)_max_level_add$", 3.0),
    (r"building_naval_administration_hiring_rate_mult$", 5.0),
    (r"country_ship_.*_construction_efficiency_add$", 6.0),
    (r"country_ship_crew_starting_veterancy_experience_add$", 4.0),
    (r"unit_experience_gain_mult$", 6.0),
    (r"unit_morale_loss_mult$", -6.0),
    (r"country_war_support_battles_increase_mult$", 4.0),
    (r"country_war_support_battles_decrease_mult$", -4.0),
    (r"country_war_support_casualties_mult$", -4.0),
    (r"country_prestige_from_navy_power_projection_mult$", 6.0),
    (r"ship_power_projection_mult$", 6.0),
    (r"country_support_separatism_(resistance|strength)_mult$", 10.0),
    (r"country_tension_decay_mult$", 8.0),
    (r"country_coup_resistance_add$", 10.0),
    (r"country_amenability_add$", 8.0),
    (r"country_bolster_attraction_factor$", 4.0),
    (r"country_acceptance_.*_add$", 2.0),
    (r"country_.*_acceptance_(min|max)_add$", 1.5),
    (r"country_primary_culture_fervor_from_laws_add$", 4.0),
    (r"country_non_state_religion_wages_mult$", 6.0),
    (r"country_state_religion_wages_mult$", 4.0),
    (r"state_.*_investment_pool_(efficiency|contribution).*$", 6.0),
    (r"interest_group_in_government_attraction_mult$", 5.0),
    (r"interest_group_ig_.*_pol_str_mult$", 0.0),
    (r"country_.*_pol_str_mult$", 0.0),
    (r"state_pop_pol_str_add$", 0.0),
    (r"state_political_strength_from_wealth_mult$", 0.0),
    (r"country_.*_voting_power.*$", 0.0),
    (r"country_electoral_confidence_impact_mult$", 0.0),
    (r"tax_land_add$", 40.0),
    (r"tax_income_add$", 50.0),
    (r"tax_per_capita_add$", 60.0),
    (r"tax_consumption_add$", 30.0),
    (r"tax_dividends_add$", 50.0),
    (r"tax_heathen_add$", 20.0),
]

RISK_RULES: list[tuple[str, float]] = [
    (r"interest_group_ig_.*_pol_str_mult$", 0.0),
    (r"country_.*_pol_str_mult$", 0.0),
    (r"state_radicals_from_political_movements_mult$", 40.0),
    (r"state_radicals_and_loyalists_from_sol_change_mult$", 20.0),
    (r"political_movement_radicalism_add$", 30.0),
    (r"building_nationalization_radicals_mult$", 30.0),
    (r"country_suppression_attraction_factor$", 25.0),
    (r"country_tension_decay_mult$", -8.0),
    (r"state_.*_mortality_mult$", 60.0),
    (r"country_allow_conversion_violent_hostility_bool$", 10.0),
    (r"country_allow_conversion_cultural_erasure_bool$", 8.0),
    (r"country_allow_conversion_open_prejudice_bool$", 5.0),
    (r"country_allow_conversion_second_rate_citizen_bool$", 4.0),
    (r"country_disallow_trade_bool$", 20.0),
    (r"country_disallow_trade_outside_.*_bool$", 10.0),
    (r"country_disallow_aggressive_plays_bool$", -5.0),
    (r"country_disallow_agitator_invites_bool$", 6.0),
    (r"country_can_only_conscript_peasants_bool$", 8.0),
    (r"country_limit_officers_qualifications_to_upper_strata$", 8.0),
    (r"state_peasants_internal_migration_disallowed_bool$", 8.0),
    (r"state_peasants_mass_migration_disallowed_bool$", 8.0),
    (r"country_disable_investment_pool_bool$", 10.0),
    (r"country_disable_nationalization_without_compensation_bool$", 10.0),
    (r"country_disable_non_company_privatization_bool$", 5.0),
    (r"country_force_privatization_bool$", -5.0),
    (r"country_disable_nationalization_bool$", -4.0),
    (r"country_forbid_monopoly_bool$", -5.0),
    (r"country_foreign_collectivization_bool$", -5.0),
    (r"tax_consumption_add$", 15.0),
    (r"country_migration_restrictiveness_add$", 15.0),
    (r"country_radicalism_increases_full_acceptance_mult$", 8.0),
    (r"country_electoral_confidence_impact_mult$", 5.0),
    (r"country_government_wages_mult$", 5.0),
    (r"country_loan_interest_rate_mult$", 5.0),
    (r"country_military_goods_cost_mult$", 5.0),
    (r"country_navy_goods_cost_mult$", 5.0),
    (r"state_bureaucracy_population_base_cost_factor_mult$", 15.0),
    (r"country_institution_cost_.*_mult$", 8.0),
    (r"country_institution_.*_max_investment_add$", 4.0),
    (r"country_bureaucracy_investment_cost_factor_mult$", 5.0),
    (r"country_legitimacy_ideological_incoherence_mult$", 20.0),
    (r"country_authority_add$", -0.02),
    (r"country_authority_mult$", -5.0),
    (r"country_legitimacy_.*_add$", -0.1),
]

COMPILED_BENEFIT = [(re.compile(p), w) for p, w in BENEFIT_RULES]
COMPILED_RISK = [(re.compile(p), w) for p, w in RISK_RULES]

BENEFIT_BY_GROUP = {
    "lawgroup_taxation": 1,
    "lawgroup_economic_system": 2,
    "lawgroup_trade_policy": 15,
    "lawgroup_land_reform": 13,
    "lawgroup_education_system": 4,
    "lawgroup_health_system": 5,
    "lawgroup_bureaucracy": 6,
    "lawgroup_governance_principles": 7,
    "lawgroup_distribution_of_power": 8,
    "lawgroup_citizenship": 10,
    "lawgroup_church_and_state": 9,
    "lawgroup_army_model": 11,
    "lawgroup_navy_model": 12,
    "lawgroup_internal_security": 16,
    "lawgroup_policing": 16,
    "lawgroup_labor_rights": 3,
    "lawgroup_labour_associations": 3,
    "lawgroup_welfare": 3,
    "lawgroup_migration": 10,
    "lawgroup_childrens_rights": 10,
    "lawgroup_rights_of_women": 8,
    "lawgroup_slavery": 10,
    "lawgroup_free_speech": 8,
    "lawgroup_colonial_affairs": 10,
    "lawgroup_caste_hegemony": 10,
    "lawgroup_edo_social_system": 10,
}

FOCUS_BY_GROUP = {
    "lawgroup_army_model": 4,
    "lawgroup_navy_model": 6,
    "lawgroup_trade_policy": 5,
}


def match_rule(rules, key: str) -> float:
    for regex, weight in rules:
        if regex.match(key):
            return weight
    return 0.0


def score_modifiers(pairs: list[tuple[str, str]]):
    benefit_total = 0.0
    risk_total = 0.0
    annotated = []
    for key, value in pairs:
        number = numeric(value)
        bw = match_rule(COMPILED_BENEFIT, key)
        rw = match_rule(COMPILED_RISK, key)
        b_contrib = max(-20.0, min(20.0, number * bw))
        r_contrib = max(-20.0, min(20.0, number * rw))
        benefit_total += b_contrib
        risk_total += r_contrib
        annotated.append(
            {
                "key": key,
                "value": value,
                "benefit": round(b_contrib, 2),
                "risk": round(r_contrib, 2),
            }
        )
    benefit = max(0, min(100, 45 + benefit_total))
    risk = max(0, min(60, 5 + risk_total))
    return round(benefit, 1), round(risk, 1), annotated


def choose_risk_theme(keys: list[str], group: str) -> int:
    joined = " ".join(keys)
    if re.search(r"landowners|aristocrats", joined):
        return 1
    if re.search(r"devout|clergymen", joined):
        return 4
    if re.search(r"officers|soldiers", joined):
        return 5
    if "rural_folk" in joined:
        return 2
    if re.search(r"trade_unions|laborers", joined):
        return 3
    if re.search(r"radicals|suppression|political_movement", joined):
        return 9
    if re.search(r"acceptance|allow_conversion|disallow_agitator|migration", joined):
        return 10
    if "disallow_trade" in joined:
        return 12
    if re.search(r"bureaucracy", joined):
        return 7
    if re.search(r"institution_cost|wages|goods_cost|consumption_tax|loan_interest", joined):
        return 6
    if re.search(r"internal_security|policing", group):
        return 9
    if re.search(r"army_model|navy_model", group):
        return 5
    return 11


def choose_focus(group: str, category: str) -> int:
    if group in FOCUS_BY_GROUP:
        return FOCUS_BY_GROUP[group]
    if category == "economy":
        return 2
    if category == "human_rights":
        return 3
    return 1


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------


def build(game: Path):
    laws_dir = game / "common" / "laws"
    groups_dir = game / "common" / "law_groups"

    groups = {}
    for path in sorted(groups_dir.glob("*.txt")):
        for name, body in top_level_blocks(path.read_text(encoding="utf-8-sig")):
            if not name.startswith("lawgroup_"):
                continue
            groups[name] = {
                "category": field_scalar(body, "law_group_category") or "power_structure",
                "enable": field_block(body, "enable"),
                "change_allowed_trigger": field_block(body, "change_allowed_trigger"),
                "base_enactment_days": field_scalar(body, "base_enactment_days"),
            }

    laws = []
    for path in sorted(laws_dir.glob("*.txt")):
        for name, body in top_level_blocks(path.read_text(encoding="utf-8-sig")):
            if not name.startswith("law_") or name == "law_group":
                continue
            group = field_scalar(body, "group") or ""
            if group not in groups:
                continue

            pair_list = flat_pairs(field_block(body, "modifier"))
            pair_list += flat_pairs(field_block(body, "institution_modifier"))
            pair_list += flat_pairs(field_block(body, "tax_modifier_medium"))

            benefit, risk, annotated = score_modifiers(pair_list)
            keys = [p[0] for p in pair_list]
            category = groups[group]["category"]
            laws.append(
                {
                    "id": name,
                    "file": path.name,
                    "group": group,
                    "category": category,
                    "benefit": benefit,
                    "risk": risk,
                    "benefit_theme": BENEFIT_BY_GROUP.get(group, 7),
                    "risk_theme": choose_risk_theme(keys, group),
                    "focus": choose_focus(group, category),
                    "modifiers": annotated,
                    "is_visible": field_block(body, "is_visible"),
                    "can_enact": field_block(body, "can_enact"),
                    "unlocking_laws": list_values(body, "unlocking_laws"),
                    "unlocking_technologies": list_values(body, "unlocking_technologies"),
                    "requires_law_or": list_values(body, "requires_law_or"),
                    "disallowing_laws": list_values(body, "disallowing_laws"),
                }
            )

    laws.sort(key=lambda law: (law["group"], law["id"]))
    for index, law in enumerate(laws, start=1):
        law["index"] = index
    return groups, laws


def as_trigger(raw: str | None, law_id: str) -> str:
    if not raw:
        return ""
    return raw.replace("scope:law", f"law_type:{law_id}")


def emit_availability(groups, laws) -> str:
    out = [
        "# Generated by tools/build_law_data.py - do not edit by hand.",
        "# One trigger per law, evaluated in country scope.",
        "",
    ]
    for law in laws:
        lid = law["id"]
        group = groups[law["group"]]
        lines = [f"sg_law_available_{lid} = {{"]
        lines.append(f"\tNOT = {{ has_law_or_variant = law_type:{lid} }}")
        if group.get("enable"):
            lines.append(indent(as_trigger(group["enable"], lid), 1).rstrip())
        if group.get("change_allowed_trigger"):
            lines.append(indent(as_trigger(group["change_allowed_trigger"], lid), 1).rstrip())
        if law["is_visible"]:
            lines.append(indent(as_trigger(law["is_visible"], lid), 1).rstrip())
        if law["can_enact"]:
            lines.append(indent(as_trigger(law["can_enact"], lid), 1).rstrip())
        if law["disallowing_laws"]:
            lines.append("\tNOT = {")
            lines.append("\t\tOR = {")
            for other in law["disallowing_laws"]:
                lines.append(f"\t\t\thas_law_or_variant = law_type:{other}")
            lines.append("\t\t}")
            lines.append("\t}")
        if law["unlocking_laws"]:
            lines.append("\tOR = {")
            for other in law["unlocking_laws"]:
                lines.append(f"\t\thas_law_or_variant = law_type:{other}")
            lines.append("\t}")
        for tech in law["unlocking_technologies"]:
            lines.append(f"\thas_technology_researched = {tech}")
        if law["requires_law_or"]:
            lines.append("\tOR = {")
            for other in law["requires_law_or"]:
                lines.append(f"\t\thas_law_or_variant = law_type:{other}")
            lines.append("\t}")
        lines.append("}")
        out.append("\n".join(lines))
        out.append("")
    return "\n".join(out)


def indent(text: str, levels: int) -> str:
    prefix = "\t" * levels
    return "\n".join(prefix + line if line.strip() else line for line in text.strip("\n").splitlines())


def dynamic_benefit(law) -> list[str]:
    theme = law["benefit_theme"]
    lines = []
    if theme == 1:
        lines.append("if = { limit = { weeks_until_bankruptcy < 52 } add = 8 }")
        lines.append("if = { limit = { net_total_income < 0 } add = 5 }")
    elif theme == 2:
        lines.append("if = { limit = { net_total_income < 0 } add = 6 }")
        lines.append("if = { limit = { average_sol < average_expected_sol } add = 4 }")
    elif theme == 3:
        lines.append("if = { limit = { average_sol < 12 } add = 6 }")
    elif theme == 4:
        lines.append("if = { limit = { literacy_rate < 0.6 } add = 6 }")
    elif theme == 5:
        lines.append("if = { limit = { average_sol < average_expected_sol } add = 5 }")
    elif theme == 6:
        lines.append("if = { limit = { approaching_bureaucracy_shortage = yes } add = 8 }")
    elif theme == 7:
        lines.append("if = { limit = { legitimacy < 50 } add = 6 }")
    elif theme in (8, 9, 10):
        lines.append("if = { limit = { radical_fraction > 0.1 } add = 5 }")
    elif theme == 11:
        lines.append("if = { limit = { is_at_war = yes } add = 8 }")
    elif theme == 12:
        lines.append("if = { limit = { is_at_war = yes } add = 6 }")
    elif theme == 13:
        lines.append("if = { limit = { average_sol < 12 } add = 4 }")
    elif theme == 14:
        lines.append("if = { limit = { net_total_income < 0 } add = 4 }")
    elif theme == 15:
        lines.append("if = { limit = { is_at_war = yes } subtract = 4 }")
        lines.append("else = { add = 3 }")
    elif theme == 16:
        lines.append("if = { limit = { radical_fraction > 0.15 } add = 6 }")
    return lines


def dynamic_risk(law) -> list[str]:
    theme = law["risk_theme"]
    lines = []
    if theme == 6:
        lines.append("if = { limit = { weeks_until_bankruptcy < 26 } add = 10 }")
    elif theme == 7:
        lines.append("if = { limit = { approaching_bureaucracy_shortage = yes } add = 8 }")
    elif theme == 8:
        lines.append("if = { limit = { legitimacy < 40 } add = 8 }")
    elif theme == 9:
        lines.append("if = { limit = { radical_fraction > 0.2 } add = 8 }")
    return lines


def emit_values(laws) -> str:
    out = [
        "# Generated by tools/build_law_data.py - do not edit by hand.",
        "# Benefit, risk, political stance and final score per law.",
        "",
    ]
    for law in laws:
        lid = law["id"]
        out.append(f"sg_law_benefit_{lid} = {{")
        out.append(f"\tvalue = {law['benefit']}")
        for line in dynamic_benefit(law):
            out.append("\t" + line)
        out.append("\tmin = 0")
        out.append("\tmax = 100")
        out.append("}")
        out.append("")

        out.append(f"sg_law_risk_{lid} = {{")
        out.append(f"\tvalue = {law['risk']}")
        for line in dynamic_risk(law):
            out.append("\t" + line)
        out.append("\tmin = 0")
        out.append("\tmax = 60")
        out.append("}")
        out.append("")

        out.append(f"sg_law_politics_{lid} = {{")
        out.append("\tvalue = 0")
        out.append("\tevery_scope_interest_group = {")
        out.append("\t\tlimit = { is_in_government = yes }")
        out.append(
            "\t\tif = { limit = { law_stance = { law = "
            f"law_type:{lid} value >= strongly_approve }} }} "
            "add = { value = ig_clout multiply = 60 } }"
        )
        out.append(
            "\t\telse_if = { limit = { law_stance = { law = "
            f"law_type:{lid} value >= approve }} }} "
            "add = { value = ig_clout multiply = 30 } }"
        )
        out.append(
            "\t\telse_if = { limit = { law_stance = { law = "
            f"law_type:{lid} value <= strongly_disapprove }} }} "
            "subtract = { value = ig_clout multiply = 60 } }"
        )
        out.append(
            "\t\telse_if = { limit = { law_stance = { law = "
            f"law_type:{lid} value <= disapprove }} }} "
            "subtract = { value = ig_clout multiply = 30 } }"
        )
        out.append("\t}")
        out.append("\tif = {")
        out.append("\t\tlimit = {")
        out.append("\t\t\texists = ruler")
        out.append(
            "\t\t\truler = { law_enactment_stance = { law = "
            f"law_type:{lid} value >= strongly_approve }} }}"
        )
        out.append("\t\t}")
        out.append("\t\tadd = 15")
        out.append("\t}")
        out.append("\telse_if = {")
        out.append("\t\tlimit = {")
        out.append("\t\t\texists = ruler")
        out.append(
            "\t\t\truler = { law_enactment_stance = { law = "
            f"law_type:{lid} value >= approve }} }}"
        )
        out.append("\t\t}")
        out.append("\t\tadd = 8")
        out.append("\t}")
        out.append("\telse_if = {")
        out.append("\t\tlimit = {")
        out.append("\t\t\texists = ruler")
        out.append(
            "\t\t\truler = { law_enactment_stance = { law = "
            f"law_type:{lid} value <= strongly_disapprove }} }}"
        )
        out.append("\t\t}")
        out.append("\t\tsubtract = 15")
        out.append("\t}")
        out.append("\telse_if = {")
        out.append("\t\tlimit = {")
        out.append("\t\t\texists = ruler")
        out.append(
            "\t\t\truler = { law_enactment_stance = { law = "
            f"law_type:{lid} value <= disapprove }} }}"
        )
        out.append("\t\t}")
        out.append("\t\tsubtract = 8")
        out.append("\t}")
        out.append("\tmin = -50")
        out.append("\tmax = 50")
        out.append("}")
        out.append("")

        out.append(f"sg_law_score_{lid} = {{")
        out.append("\tvalue = 0")
        out.append("\tif = {")
        out.append(f"\t\tlimit = {{ sg_law_available_{lid} = yes }}")
        out.append(f"\t\tadd = {{ value = sg_law_benefit_{lid} }}")
        out.append(f"\t\tadd = {{ value = sg_law_politics_{lid} }}")
        out.append(f"\t\tsubtract = {{ value = sg_law_risk_{lid} multiply = 0.5 }}")
        out.append("\t}")
        out.append("\tmin = -100")
        out.append("\tmax = 200")
        out.append("}")
        out.append("")
    return "\n".join(out)


def ignored_trigger(law) -> str:
    parts = []
    for slot in (1, 2, 3):
        parts.append(
            f"AND = {{ has_variable = sg_ignored_{slot} "
            f"var:sg_ignored_{slot} = {law['index']} }}"
        )
    return "NOT = { OR = { " + " ".join(parts) + " } }"


def shift_effects() -> str:
    fields = ["law", "index", "score", "benefit", "risk", "focus", "benefit_score", "risk_score", "politics"]
    out = ["# Generated by tools/build_law_data.py - do not edit by hand.", ""]
    for source, target in (("1", "2"), ("2", "3")):
        name = f"sg_copy_top_{source}_to_{target}"
        out.append(f"{name} = {{")
        for field in fields:
            out.append(
                f"\tset_variable = {{ name = sg_top_{target}_{field} "
                f"value = var:sg_top_{source}_{field} }}"
            )
        out.append("}")
        out.append("")
    out.append("sg_shift_top_for_1 = {")
    out.append("\tif = { limit = { has_variable = sg_top_2_law } sg_copy_top_2_to_3 = yes }")
    out.append("\tif = { limit = { has_variable = sg_top_1_law } sg_copy_top_1_to_2 = yes }")
    out.append("}")
    out.append("")
    out.append("sg_shift_top_for_2 = {")
    out.append("\tif = { limit = { has_variable = sg_top_2_law } sg_copy_top_2_to_3 = yes }")
    out.append("}")
    out.append("")
    return "\n".join(out)


def store_block(law, slot: int) -> str:
    lid = law["id"]
    return "\n".join(
        [
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_law value = law_type:{lid} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_index value = {law['index']} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_score value = sg_law_score_{lid} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_benefit value = {law['benefit_theme']} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_risk value = {law['risk_theme']} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_focus value = {law['focus']} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_benefit_score value = sg_law_benefit_{lid} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_risk_score value = sg_law_risk_{lid} }}",
            f"\t\t\tset_variable = {{ name = sg_top_{slot}_politics value = sg_law_politics_{lid} }}",
        ]
    )


def emit_rank(laws) -> str:
    out = ["# Generated by tools/build_law_data.py - do not edit by hand.", ""]
    out.append("sg_rank_laws = {")
    fields = ["law", "index", "benefit", "risk", "focus", "benefit_score", "risk_score", "politics"]
    for slot in (1, 2, 3):
        for field in fields:
            out.append(f"\tremove_variable = sg_top_{slot}_{field}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_score value = -1000 }}")
    out.append("")
    for law in laws:
        lid = law["id"]
        score = f"sg_law_score_{lid}"
        out.append(f"\tif = {{")
        out.append(f"\t\tlimit = {{")
        out.append(f"\t\t\tsg_law_available_{lid} = yes")
        out.append(f"\t\t\t{ignored_trigger(law)}")
        out.append(f"\t\t}}")
        out.append(f"\t\tif = {{")
        out.append(f"\t\t\tlimit = {{ {score} > var:sg_top_1_score }}")
        out.append("\t\t\tsg_shift_top_for_1 = yes")
        out.append(store_block(law, 1))
        out.append("\t\t}")
        out.append(f"\t\telse_if = {{")
        out.append(f"\t\t\tlimit = {{ {score} > var:sg_top_2_score }}")
        out.append("\t\t\tsg_shift_top_for_2 = yes")
        out.append(store_block(law, 2))
        out.append("\t\t}")
        out.append(f"\t\telse_if = {{")
        out.append(f"\t\t\tlimit = {{ {score} > var:sg_top_3_score }}")
        out.append(store_block(law, 3))
        out.append("\t\t}")
        out.append("\t}")
    out.append("}")
    out.append("")
    return "\n".join(out)


def emit_actions(laws) -> str:
    out = ["# Generated by tools/build_law_data.py - do not edit by hand.", ""]
    out.append("sg_enact_selected = {")
    for law in laws:
        lid = law["id"]
        out.append(f"\tif = {{")
        out.append(f"\t\tlimit = {{ var:sg_selected_index = {law['index']} }}")
        out.append(f"\t\tif = {{")
        out.append(f"\t\t\tlimit = {{ sg_law_available_{lid} = yes NOT = {{ enacting_any_law = yes }} }}")
        out.append(f"\t\t\tstart_enactment = law_type:{lid}")
        out.append("\t\t\tsg_rank_laws = yes")
        out.append("\t\t}")
        out.append("\t}")
    out.append("}")
    out.append("")
    for slot in (1, 2, 3):
        out.append(f"sg_enact_top_{slot} = {{")
        out.append(f"\tif = {{")
        out.append(f"\t\tlimit = {{ has_variable = sg_top_{slot}_index }}")
        out.append(f"\t\tset_variable = {{ name = sg_selected_index value = var:sg_top_{slot}_index }}")
        out.append("\t\tsg_enact_selected = yes")
        out.append("\t\tremove_variable = sg_selected_index")
        out.append("\t}")
        out.append("}")
        out.append("")
    return "\n".join(out)


def emit_loc(laws, lang: str) -> str:
    pt = lang == "braz_por"

    def L(en: str, ptbr: str) -> str:
        return ptbr if pt else en

    themes = {
        "benefit": [
            L("Improves fiscal capacity and tax collection.", "Melhora a capacidade fiscal e a arrecadação de impostos."),
            L("Strengthens the wider economy and private investment.", "Fortalece a economia e o investimento privado."),
            L("Improves wages, working conditions and welfare.", "Melhora salários, condições de trabalho e bem-estar."),
            L("Raises education access and literacy.", "Amplia o acesso à educação e a alfabetização."),
            L("Improves public health and reduces mortality.", "Melhora a saúde pública e reduz a mortalidade."),
            L("Makes the state administration more efficient.", "Torna a administração estatal mais eficiente."),
            L("Strengthens central authority and legitimacy.", "Fortalece a autoridade central e a legitimidade."),
            L("Broadens political inclusion and participation.", "Amplia a inclusão e a participação política."),
            L("Reduces religious discrimination and tension.", "Reduz a discriminação e a tensão religiosa."),
            L("Improves acceptance and integration of minorities.", "Melhora a aceitação e a integração de minorias."),
            L("Strengthens the army and military readiness.", "Fortalece o exército e a prontidão militar."),
            L("Strengthens the navy and naval industry.", "Fortalece a marinha e a indústria naval."),
            L("Improves agriculture and rural living standards.", "Melhora a agricultura e o padrão de vida rural."),
            L("Supports construction and infrastructure.", "Apoia a construção e a infraestrutura."),
            L("Improves trade access and market reach.", "Melhora o acesso ao comércio e ao mercado."),
            L("Improves internal security and public order.", "Melhora a segurança interna e a ordem pública."),
        ],
        "risk": [
            L("May provoke landowner and aristocratic backlash.", "Pode provocar reação de latifundiários e aristocratas."),
            L("May anger the rural population.", "Pode irritar a população rural."),
            L("May trigger urban and worker unrest.", "Pode causar agitação urbana e operária."),
            L("May provoke the devout and the clergy.", "Pode provocar os devotos e o clero."),
            L("May alienate the armed forces.", "Pode alienar as forças armadas."),
            L("Puts pressure on the budget and treasury.", "Pressiona o orçamento e o tesouro."),
            L("Adds strain on the bureaucracy.", "Aumenta a pressão sobre a burocracia."),
            L("May reduce legitimacy if society is not ready.", "Pode reduzir a legitimidade se a sociedade não estiver pronta."),
            L("May increase radicalism and political violence.", "Pode aumentar o radicalismo e a violência política."),
            L("May deepen discrimination or social exclusion.", "Pode aprofundar a discriminação ou a exclusão social."),
            L("Creates tension between central power and local autonomy.", "Cria tensão entre o poder central e a autonomia local."),
            L("May isolate the economy or invite diplomatic friction.", "Pode isolar a economia ou gerar atrito diplomático."),
        ],
        "focus": [
            L("Governance", "Governança"),
            L("Economy", "Economia"),
            L("Society", "Sociedade"),
            L("Military", "Militar"),
            L("Trade", "Comércio"),
            L("Navy", "Marinha"),
        ],
    }

    out = [f"l_{lang}:"]
    for i, text in enumerate(themes["benefit"], start=1):
        out.append(f' sg_benefit_{i}:0 "{text}"')
    for i, text in enumerate(themes["risk"], start=1):
        out.append(f' sg_risk_{i}:0 "{text}"')
    for i, text in enumerate(themes["focus"], start=1):
        out.append(f' sg_focus_{i}:0 "{text}"')
    out.append("")
    for law in laws:
        lid = law["id"]
        benefit_text = themes["benefit"][law["benefit_theme"] - 1]
        risk_text = themes["risk"][law["risk_theme"] - 1]
        # Per-law strings are kept for the JSON dump and for modders; the GUI
        # renders the theme through a compact localization selector.
        out.append(f' sg_law_benefit_{lid}:0 "{benefit_text}"')
        out.append(f' sg_law_risk_{lid}:0 "{risk_text}"')
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default=str(DEFAULT_GAME))
    parser.add_argument("--out", default=str(Path(__file__).resolve().parent.parent))
    args = parser.parse_args()

    game = Path(args.game)
    out = Path(args.out)
    groups, laws = build(game)
    if not laws:
        print("No laws parsed; check --game", file=sys.stderr)
        return 1

    (out / "common" / "scripted_triggers").mkdir(parents=True, exist_ok=True)
    (out / "common" / "script_values").mkdir(parents=True, exist_ok=True)
    (out / "common" / "scripted_effects").mkdir(parents=True, exist_ok=True)
    (out / "localization" / "english").mkdir(parents=True, exist_ok=True)
    (out / "localization" / "braz_por").mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(parents=True, exist_ok=True)

    (out / "common" / "scripted_triggers" / "sg_law_availability.txt").write_text(
        emit_availability(groups, laws), encoding="utf-8"
    )
    (out / "common" / "script_values" / "sg_law_scores.txt").write_text(
        emit_values(laws), encoding="utf-8"
    )
    (out / "common" / "scripted_effects" / "sg_law_rank.txt").write_text(
        shift_effects() + emit_rank(laws), encoding="utf-8"
    )
    (out / "common" / "scripted_effects" / "sg_law_actions.txt").write_text(
        emit_actions(laws), encoding="utf-8"
    )
    (out / "localization" / "english" / "sg_generated_l_english.yml").write_text(
        emit_loc(laws, "english"), encoding="utf-8-sig"
    )
    (out / "localization" / "braz_por" / "sg_generated_l_braz_por.yml").write_text(
        emit_loc(laws, "braz_por"), encoding="utf-8-sig"
    )
    (out / "data" / "law_data.json").write_text(
        json.dumps({"groups": groups, "laws": laws}, indent=1, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {len(laws)} laws across {len(groups)} groups.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
