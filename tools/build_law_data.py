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
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdx_parse import parse, strip_comments  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LAW_IDS_FILE = ROOT / "data" / "law_ids.json"
SCHEMA_VERSION = 2
TAX_BRACKETS = ("very_low", "low", "medium", "high", "very_high")
# 1.15 defines live under a namespace (NCountry, NPolitics, NWar, ...). The
# un-namespaced form is rejected at load time with "Invalid define, expected
# 'Namespace|Name'". LAW_MIN_SUCCESS_CHANCE is defined in NPolitics.
MIN_SUCCESS_CHANCE_DEFINE = "define:NPolitics|LAW_MIN_SUCCESS_CHANCE"
# A law only enters the recommendations when its merit beats the law already
# in force in its group by this margin. The point is to avoid filling the list
# with alternatives that are effectively sidegrades.
MIN_IMPROVEMENT = 5.0


def game_candidates() -> list[Path]:
    """Portable locations to try before giving up on automatic discovery."""
    candidates: list[Path] = []
    env = os.environ.get("VICTORIA3_GAME")
    if env:
        candidates.append(Path(env).expanduser())
    candidates.append(Path.cwd() / "game")
    candidates.append(ROOT / "game")

    home = Path.home()
    steam_roots = [
        home / ".steam" / "steam",
        home / ".local" / "share" / "Steam",
        home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
        Path("C:/Program Files (x86)/Steam"),
        Path("C:/Program Files/Steam"),
        home / "Library" / "Application Support" / "Steam",
    ]
    for steam in steam_roots:
        candidates.append(steam / "steamapps" / "common" / "Victoria 3" / "game")

    # Common manual installs (including the layout used by this project).
    games = home / "Games"
    candidates.append(games / "Victoria 3" / "game")
    if games.is_dir():
        candidates.extend(path / "game" for path in games.iterdir() if path.is_dir())

    # Hydra and other Wine launchers: the prefix name is not fixed, so scan.
    for prefixes in (
        home / ".config" / "hydralauncher" / "wine-prefixes",
        home / ".local" / "share" / "hydralauncher" / "wine-prefixes",
    ):
        if not prefixes.is_dir():
            continue
        for prefix in prefixes.iterdir():
            drive = prefix / "drive_c"
            candidates.extend(
                [
                    drive / "Program Files (x86)" / "Steam" / "steamapps" / "common" / "Victoria 3" / "game",
                    drive / "Program Files" / "Steam" / "steamapps" / "common" / "Victoria 3" / "game",
                    drive / "Games" / "Victoria 3" / "game",
                ]
            )
    return candidates


def resolve_game_path(value: str | None) -> Path:
    """Accept an install root, a game folder, or discover a normal install."""
    if value:
        raw = Path(value).expanduser()
        if (raw / "common" / "laws").is_dir():
            return raw
        if (raw / "game" / "common" / "laws").is_dir():
            return raw / "game"
        raise SystemExit(
            f"Could not find common/laws under {raw}. Point --game at the Victoria 3 "
            "'game' folder (the one that contains common/ and gui/)."
        )
    for candidate in game_candidates():
        if (candidate / "common" / "laws").is_dir():
            return candidate
        if (candidate / "game" / "common" / "laws").is_dir():
            return candidate / "game"
    raise SystemExit(
        "Could not find Victoria 3 automatically. Run with "
        "--game '/path/to/Victoria 3/game' or set VICTORIA3_GAME."
    )


def load_law_ids() -> dict[str, int]:
    if not LAW_IDS_FILE.is_file():
        return {}
    try:
        raw = json.loads(LAW_IDS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return {str(k): int(v) for k, v in raw.items()}


def assign_stable_ids(laws: list[dict], mapping: dict[str, int]) -> dict[str, int]:
    """Give every law a numeric id that never changes when the list is reordered.

    Existing ids are preserved from data/law_ids.json. New laws get the next
    free number. Ids of removed laws stay reserved so they are never reused for
    a different law in an old save.
    """
    used = set(mapping.values())
    next_id = max(used, default=0) + 1
    for law in sorted(laws, key=lambda item: item["id"]):
        if law["id"] not in mapping:
            mapping[law["id"]] = next_id
            next_id += 1
    for law in laws:
        law["sid"] = mapping[law["id"]]
    return mapping

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
    (r"state_.*mortality_mult$", -60.0),
    (r"state_.*standard_of_living_add$", 25.0),
    (r"state_.*expected_sol_(add|mult)$", 12.0),
    (r"state_birth_rate_mult$", 20.0),
    (r"state_working_adult_ratio_add$", 25.0),
    (r"state_dependent_wage_mult$", 8.0),
    (r"building_minimum_wage_mult$", 30.0),
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
    (r"state_.*investment_pool_(efficiency|contribution).*$", 6.0),
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
    (r"state_.*mortality_mult$", 60.0),
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

# Benefit themes are selected from the law's *positive* modifier
# contributions, never from its group. Two laws in the same group can have
# opposite effects (autocracy vs. universal suffrage), so a group-wide claim is
# misleading.
BENEFIT_THEME_RULES: list[tuple[str, int]] = [
    (r"education_access|qualification|literacy|research", 4),
    (r"mortality|health|standard_of_living|birth_rate|working_adult|dependent_wage", 5),
    (r"bureaucracy|institution_cost", 6),
    (r"religion", 9),
    (r"acceptance|cultural|assimilation|conversion|migration", 10),
    (r"army|conscription|morale|war_support|officer", 11),
    (r"navy|ship|naval", 12),
    (r"agriculture|rural|subsistence|arable|land", 13),
    (r"construction|infrastructure|investment_pool", 14),
    (r"trade|tariff|market_access|import|export", 15),
    (r"internal_security|policing|radicals|suppression", 16),
    (r"wage|welfare|labor|working", 3),
    (r"tax|income|dividend", 1),
    (r"throughput|investment|company|private_construction|loan_interest|goods_cost|government_wages|free_charters|max_companies|nationalization|subvention|production", 2),
    # Authority/legitimacy is deliberately late: a law that broadens political
    # participation should be described by that real effect, not by legitimacy.
    (r"authority|legitimacy", 7),
]

BENEFIT_NEUTRAL_THEME = 17
BENEFIT_GENERIC_THEME = 18
RISK_NEUTRAL_THEME = 13

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
    return round(benefit_total, 2), round(risk_total, 2), annotated


def choose_benefit_theme(annotated: list[dict]) -> int:
    """Describe only effects the law actually has.

    A law with no positive measurable modifier (for example law_no_schools,
    whose modifier block is empty) gets the neutral theme instead of a
    positive group claim.
    """
    positive = [item["key"] for item in annotated if item["benefit"] > 0]
    if not positive:
        return BENEFIT_NEUTRAL_THEME
    joined = " ".join(positive)
    for pattern, theme in BENEFIT_THEME_RULES:
        if re.search(pattern, joined):
            return theme
    # The law does have a measurable positive effect, but none of the specific
    # families above describe it. A generic state-capacity sentence is safer
    # than claiming "no bonus" while the score includes a real contribution.
    return BENEFIT_GENERIC_THEME


def choose_risk_theme(group: str, annotated: list[dict]) -> int:
    """Describe only risks the law actually carries.

    Like the benefit theme, this uses the sign of the real risk contribution,
    never the law group alone. A law that reduces radicalism must not display
    "may increase radicalism" because it belongs to the policing group.
    """
    positive = [item["key"] for item in annotated if item["risk"] > 0]
    if not positive:
        return RISK_NEUTRAL_THEME
    joined = " ".join(positive)
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
    # Positive contribution with no specific family: the generic risk sentence
    # may be vague, but it is truthful about the law's direction.
    if re.search(r"internal_security|policing|army_model|navy_model", group):
        return 9
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

            # Tax laws define a different block per tax level. Score the
            # average per key so low/high brackets are not silently ignored.
            tax_values: dict[str, list[float]] = {}
            for bracket in TAX_BRACKETS:
                for key, value in flat_pairs(field_block(body, f"tax_modifier_{bracket}")):
                    tax_values.setdefault(key, []).append(numeric(value))
            tax_pairs = [
                (key, str(round(sum(values) / len(values), 4)))
                for key, values in tax_values.items()
            ]
            pair_list += tax_pairs

            benefit_total, risk_total, annotated = score_modifiers(pair_list)
            category = groups[group]["category"]
            benefit_theme = choose_benefit_theme(annotated)
            # A law with no positive measurable effect must not inherit the
            # baseline that laws with real benefits receive.
            has_positive_signal = any(item["benefit"] > 0 for item in annotated)
            benefit = max(0, min(100, (45 if has_positive_signal else 30) + benefit_total))
            risk = max(0, min(60, 5 + risk_total))
            laws.append(
                {
                    "id": name,
                    "file": path.name,
                    "group": group,
                    "category": category,
                    "benefit": round(benefit, 1),
                    "risk": round(risk, 1),
                    "benefit_theme": benefit_theme,
                    "risk_theme": choose_risk_theme(group, annotated),
                    "focus": choose_focus(group, category),
                    "has_positive_signal": has_positive_signal,
                    "modifiers": annotated,
                    "tax_brackets": {
                        key: round(sum(values) / len(values), 4)
                        for key, values in tax_values.items()
                    },
                    "is_visible": field_block(body, "is_visible"),
                    "can_enact": field_block(body, "can_enact"),
                    "unlocking_laws": list_values(body, "unlocking_laws"),
                    "unlocking_technologies": list_values(body, "unlocking_technologies"),
                    "requires_law_or": list_values(body, "requires_law_or"),
                    "disallowing_laws": list_values(body, "disallowing_laws"),
                }
            )

    laws.sort(key=lambda law: (law["group"], law["id"]))
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
        lines.append("\tNOT = { enacting_any_law = yes }")
        lines.append(
            f'\t"enactment_chance_for_law(law_type:{lid})" >= '
            f"{MIN_SUCCESS_CHANCE_DEFINE}"
        )
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
        # radical_fraction is a block trigger in 1.15, not a script value.
        lines.append("if = { limit = { radical_fraction = { value >= 0.1 } } add = 5 }")
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
        lines.append("if = { limit = { radical_fraction = { value >= 0.15 } } add = 6 }")
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
        lines.append("if = { limit = { radical_fraction = { value >= 0.2 } } add = 8 }")
    lines.append(
        "if = { limit = { any_interest_group = { "
        "is_powerful = yes "
        f"law_stance = {{ law = law_type:{law['id']} value <= strongly_disapprove }} "
        "} } add = 12 }"
    )
    return lines


def emit_values(laws) -> str:
    out = [
        "# Generated by tools/build_law_data.py - do not edit by hand.",
        "# Benefit, risk, political stance, viability and final score per law.",
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
        out.append("\tevery_interest_group = {")
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

        out.append(f"sg_law_enactment_chance_{lid} = {{")
        out.append(f'\tvalue = "enactment_chance_for_law(law_type:{lid})"')
        out.append("\tmultiply = 100")
        out.append("\tmin = 0")
        out.append("\tmax = 100")
        out.append("}")
        out.append("")

        # Merit measures whether the law improves the country: benefit plus
        # government support minus half of the risk. Enactment chance is a
        # viability factor, so it belongs to the ranking score but not to the
        # improvement comparison against the current law.
        out.append(f"sg_law_merit_{lid} = {{")
        out.append("\tvalue = 0")
        out.append(f"\tadd = {{ value = sg_law_benefit_{lid} }}")
        out.append(f"\tadd = {{ value = sg_law_politics_{lid} }}")
        out.append(f"\tsubtract = {{ value = sg_law_risk_{lid} multiply = 0.5 }}")
        out.append("\tmin = -100")
        out.append("\tmax = 150")
        out.append("}")
        out.append("")

        out.append(f"sg_law_score_{lid} = {{")
        out.append("\tvalue = 0")
        out.append("\tif = {")
        out.append(f"\t\tlimit = {{ sg_law_available_{lid} = yes }}")
        out.append(f"\t\tadd = {{ value = sg_law_merit_{lid} }}")
        out.append(
            f"\t\tadd = {{ value = sg_law_enactment_chance_{lid} multiply = 0.5 }}"
        )
        out.append("\t}")
        out.append("\tmin = -100")
        out.append("\tmax = 200")
        out.append("}")
        out.append("")

    by_group: dict[str, list[dict]] = {}
    for law in laws:
        by_group.setdefault(law["group"], []).append(law)
    for group in sorted(by_group):
        out.append(f"sg_law_current_merit_{group} = {{")
        out.append("\tvalue = 0")
        for law in sorted(by_group[group], key=lambda item: item["sid"]):
            # Use the exact law, not has_law_or_variant: a law and its variant
            # can both match the variant check, which would add two merits.
            out.append("\tif = {")
            out.append(f"\t\tlimit = {{ has_law = law_type:{law['id']} }}")
            out.append(f"\t\tadd = {{ value = sg_law_merit_{law['id']} }}")
            out.append("\t}")
        out.append("\tmin = -100")
        out.append("\tmax = 150")
        out.append("}")
        out.append("")
        # The comparison is done against the current law's merit plus the
        # minimum improvement, so a tie or a sidegrade never fills a slot.
        out.append(f"sg_law_upgrade_floor_{group} = {{")
        out.append(f"\tvalue = sg_law_current_merit_{group}")
        out.append(f"\tadd = {MIN_IMPROVEMENT}")
        out.append("}")
        out.append("")
    return "\n".join(out)


def ignored_trigger(law) -> str:
    return f"NOT = {{ {ignored_list_trigger(law)} }}"


def ignored_list_trigger(law) -> str:
    parts = []
    for slot in (1, 2, 3):
        parts.append(
            f"AND = {{ has_variable = sg_ignored_{slot} "
            f"var:sg_ignored_{slot} = {law['sid']} }}"
        )
    return "OR = { " + " ".join(parts) + " }"


def shift_effects() -> str:
    fields = [
        "id",
        "score",
        "benefit",
        "risk",
        "focus",
        "benefit_score",
        "risk_score",
        "politics",
        "enactment_chance",
    ]
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
    out.append("\tif = { limit = { has_variable = sg_top_2_id } sg_copy_top_2_to_3 = yes }")
    out.append("\tif = { limit = { has_variable = sg_top_1_id } sg_copy_top_1_to_2 = yes }")
    out.append("}")
    out.append("")
    out.append("sg_shift_top_for_2 = {")
    out.append("\tif = { limit = { has_variable = sg_top_2_id } sg_copy_top_2_to_3 = yes }")
    out.append("}")
    out.append("")
    return "\n".join(out)


def store_block(law, slot: int, indent: int = 3) -> str:
    lid = law["id"]
    pad = "\t" * indent
    return "\n".join(
        [
            f"{pad}set_variable = {{ name = sg_top_{slot}_id value = {law['sid']} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_score value = sg_law_score_{lid} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_benefit value = {law['benefit_theme']} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_risk value = {law['risk_theme']} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_focus value = {law['focus']} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_benefit_score value = sg_law_benefit_{lid} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_risk_score value = sg_law_risk_{lid} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_politics value = sg_law_politics_{lid} }}",
            f"{pad}set_variable = {{ name = sg_top_{slot}_enactment_chance value = sg_law_enactment_chance_{lid} }}",
        ]
    )


def emit_rank(laws) -> str:
    out = ["# Generated by tools/build_law_data.py - do not edit by hand.", ""]
    out.append("sg_rank_laws = {")
    # Migrate a save created by the old positional-index schema before any
    # stored id is compared.
    out.append("\tsg_migrate_schema = yes")
    out.append("\tset_variable = { name = sg_last_refresh_year value = year }")
    out.append("\tset_variable = { name = sg_last_refresh_month value = month }")
    out.append(f"\tset_variable = {{ name = sg_last_rank_evaluated value = {len(laws)} }}")
    out.append("\tset_variable = { name = sg_last_rank_available value = 0 }")
    out.append("\tset_variable = { name = sg_last_rank_ignored value = 0 }")
    out.append("\tset_variable = { name = sg_last_rank_upgrade_filtered value = 0 }")
    out.append("\tset_variable = { name = sg_last_rank_eligible value = 0 }")
    out.append("\tset_variable = { name = sg_last_ranked_count value = 0 }")
    fields = [
        "id",
        "benefit",
        "risk",
        "focus",
        "benefit_score",
        "risk_score",
        "politics",
        "enactment_chance",
    ]
    for slot in (1, 2, 3):
        for field in fields:
            out.append(f"\tremove_variable = sg_top_{slot}_{field}")
        # Keep the id variable present with a sentinel so the widget never asks
        # GetValue on a missing variable. Id 0 matches no generated law branch.
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_id value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_benefit value = 17 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_risk value = 13 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_focus value = 1 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_benefit_score value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_risk_score value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_politics value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_enactment_chance value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_score value = -1000 }}")
    out.append("")
    for law in laws:
        lid = law["id"]
        score = f"sg_law_score_{lid}"
        out.append(f"\tif = {{")
        out.append(f"\t\tlimit = {{")
        out.append(f"\t\t\tsg_law_available_{lid} = yes")
        out.append(f"\t\t}}")
        out.append("\t\tchange_variable = { name = sg_last_rank_available add = 1 }")
        out.append("\t\tif = {")
        out.append(f"\t\t\tlimit = {{ {ignored_list_trigger(law)} }}")
        out.append("\t\t\tchange_variable = { name = sg_last_rank_ignored add = 1 }")
        out.append("\t\t}")
        out.append("\t\telse = {")
        # Rank globally, but only keep laws that improve on the law currently
        # in force in their own group. The comparison is merit (benefit +
        # government support - half the risk) against the group's current law
        # plus MIN_IMPROVEMENT. No qualifying law means an empty list, never a
        # forced recommendation.
        out.append("\t\t\tif = {")
        out.append(
            f"\t\t\t\tlimit = {{ sg_law_merit_{lid} >= "
            f"sg_law_upgrade_floor_{law['group']} }}"
        )
        out.append("\t\t\t\tchange_variable = { name = sg_last_rank_eligible add = 1 }")
        out.append("\t\t\t\tif = {")
        out.append(f"\t\t\t\t\tlimit = {{ {score} > var:sg_top_1_score }}")
        out.append("\t\t\t\t\tsg_shift_top_for_1 = yes")
        out.append(store_block(law, 1, 5))
        out.append("\t\t\t\t}")
        out.append("\t\t\t\telse_if = {")
        out.append(f"\t\t\t\t\tlimit = {{ {score} > var:sg_top_2_score }}")
        out.append("\t\t\t\t\tsg_shift_top_for_2 = yes")
        out.append(store_block(law, 2, 5))
        out.append("\t\t\t\t}")
        out.append("\t\t\t\telse_if = {")
        out.append(f"\t\t\t\t\tlimit = {{ {score} > var:sg_top_3_score }}")
        out.append(store_block(law, 3, 5))
        out.append("\t\t\t\t}")
        out.append("\t\t\t}")
        out.append("\t\t\telse = {")
        out.append("\t\t\t\tchange_variable = { name = sg_last_rank_upgrade_filtered add = 1 }")
        out.append("\t\t\t}")
        out.append("\t\t}")
        out.append("\t}")
    out.append("\tif = { limit = { var:sg_top_1_id > 0 } change_variable = { name = sg_last_ranked_count add = 1 } }")
    out.append("\tif = { limit = { var:sg_top_2_id > 0 } change_variable = { name = sg_last_ranked_count add = 1 } }")
    out.append("\tif = { limit = { var:sg_top_3_id > 0 } change_variable = { name = sg_last_ranked_count add = 1 } }")
    out.append("}")
    out.append("")
    return "\n".join(out)


def emit_actions(laws) -> str:
    """One enact/ignore effect per law.

    The GUI button for a law calls that law's effect directly, so a rerank
    between rendering and clicking can never redirect the action to a different
    recommendation by slot number.
    """
    out = ["# Generated by tools/build_law_data.py - do not edit by hand.", ""]
    for law in laws:
        lid = law["id"]
        sid = law["sid"]
        out.append(f"sg_enact_law_{lid} = {{")
        out.append("\tif = {")
        out.append(f"\t\tlimit = {{ sg_law_available_{lid} = yes NOT = {{ enacting_any_law = yes }} }}")
        out.append(f"\t\tstart_enactment = law_type:{lid}")
        out.append("\t}")
        out.append("\t# Rerank even when the guard failed: the row is stale and must")
        out.append("\t# disappear or change instead of looking like a dead click.")
        out.append("\tsg_rank_laws = yes")
        out.append("}")
        out.append("")
        out.append(f"sg_ignore_law_{lid} = {{")
        out.append(f"\tset_variable = {{ name = sg_ignored_selected value = {sid} }}")
        out.append("\tsg_store_ignored_selected = yes")
        out.append("\tremove_variable = sg_ignored_selected")
        out.append("\tsg_rank_laws = yes")
        out.append("}")
        out.append("")
    return "\n".join(out)


def emit_sguis(laws) -> str:
    out = [
        "# Generated by tools/build_law_data.py - do not edit by hand.",
        "# One scripted GUI per law and action, so each button is bound to the",
        "# law it displays rather than to a mutable recommendation slot.",
        "",
    ]
    for law in laws:
        lid = law["id"]
        out.append(f"sg_enact_law_{lid}_sgui = {{")
        out.append("\tscope = country")
        out.append("\tis_shown = { is_player = yes has_variable = sg_enabled }")
        # Availability is checked inside the effect, not in is_valid: if the law
        # became unavailable the button must still be clickable so the click
        # can rerank and remove the stale row.
        out.append("\tis_valid = { sg_can_start_enactment = yes }")
        out.append(f"\teffect = {{ sg_enact_law_{lid} = yes }}")
        out.append("}")
        out.append("")
        out.append(f"sg_ignore_law_{lid}_sgui = {{")
        out.append("\tscope = country")
        out.append("\tis_shown = { is_player = yes has_variable = sg_enabled }")
        out.append("\tis_valid = { is_player = yes has_variable = sg_enabled }")
        out.append(f"\teffect = {{ sg_ignore_law_{lid} = yes }}")
        out.append("}")
        out.append("")
        sid = law["sid"]
        for slot in (1, 2, 3):
            out.append(f"sg_top_{slot}_law_{lid}_visible_sgui = {{")
            out.append("\tscope = country")
            out.append(
                f"\tis_shown = {{ has_variable = sg_top_{slot}_id "
                f"var:sg_top_{slot}_id = {sid} }}"
            )
            out.append("}")
            out.append("")
            out.append(f"sg_ignored_{slot}_law_{lid}_visible_sgui = {{")
            out.append("\tscope = country")
            out.append(
                f"\tis_shown = {{ has_variable = sg_ignored_{slot} "
                f"var:sg_ignored_{slot} = {sid} }}"
            )
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
            L("No direct measurable bonus; it mainly changes the legal framework.", "Sem bônus direto mensurável; a lei principalmente altera o marco legal."),
            L("Has positive measurable effects included in the benefit score.", "Tem efeitos positivos mensuráveis incluídos na pontuação de benefício."),
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
            L("May create costs, rigidity or political tension.", "Pode gerar custos, rigidez ou tensão política."),
            L("May isolate the economy or invite diplomatic friction.", "Pode isolar a economia ou gerar atrito diplomático."),
            L("No direct measurable risk beyond the normal enactment process.", "Sem risco direto mensurável além do processo normal de promulgação."),
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
    # Index 0 is the safe fallback while a row variable is being written.
    out.append(f' sg_benefit_0:0 "{themes["benefit"][BENEFIT_NEUTRAL_THEME - 1]}"')
    for i, text in enumerate(themes["benefit"], start=1):
        out.append(f' sg_benefit_{i}:0 "{text}"')
    out.append(f' sg_risk_0:0 "{themes["risk"][RISK_NEUTRAL_THEME - 1]}"')
    for i, text in enumerate(themes["risk"], start=1):
        out.append(f' sg_risk_{i}:0 "{text}"')
    out.append(f' sg_focus_0:0 "{themes["focus"][0]}"')
    for i, text in enumerate(themes["focus"], start=1):
        out.append(f' sg_focus_{i}:0 "{text}"')
    out.append("")
    effect_label = L("Effects:", "Efeitos:")
    req_label = L("Requirements:", "Requisitos:")
    for law in laws:
        lid = law["id"]
        sid = law["sid"]
        benefit_text = themes["benefit"][law["benefit_theme"] - 1]
        risk_text = themes["risk"][law["risk_theme"] - 1]
        # The GUI selects these by stable numeric id. GetLawType is a global
        # localization function, so the row never depends on a law-type value
        # stored in a country variable.
        out.append(f' sg_law_name_{sid}:0 "[GetLawType(\'{lid}\').GetName]"')
        out.append(f' sg_law_group_{sid}:0 "[GetLawType(\'{lid}\').GetGroup.GetName]"')
        out.append(
            f' sg_law_tip_{sid}:0 "{effect_label}\\n'
            f"[GetLawType('{lid}').GetEffectDesc(GetPlayer.Self)]\\n\\n"
            f"{req_label}\\n[GetLawType('{lid}').GetBlockingRequirements(GetPlayer.Self)]\""
        )
        out.append(f' sg_law_benefit_{lid}:0 "{benefit_text}"')
        out.append(f' sg_law_risk_{lid}:0 "{risk_text}"')
    return "\n".join(out) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--game",
        default=None,
        help="Victoria 3 game folder (contains common/ and gui/). "
        "Defaults to VICTORIA3_GAME or automatic Steam/Hydra discovery.",
    )
    parser.add_argument("--out", default=str(ROOT))
    args = parser.parse_args()

    game = resolve_game_path(args.game)
    out = Path(args.out)
    groups, laws = build(game)
    if not laws:
        print(f"No laws parsed under {game}; check --game", file=sys.stderr)
        return 1
    law_ids = assign_stable_ids(laws, load_law_ids())

    (out / "common" / "scripted_triggers").mkdir(parents=True, exist_ok=True)
    (out / "common" / "script_values").mkdir(parents=True, exist_ok=True)
    (out / "common" / "scripted_effects").mkdir(parents=True, exist_ok=True)
    (out / "localization" / "english").mkdir(parents=True, exist_ok=True)
    (out / "localization" / "braz_por").mkdir(parents=True, exist_ok=True)
    (out / "data").mkdir(parents=True, exist_ok=True)

    # 1.15 asks every script file for a UTF-8 BOM; without it the file is still
    # parsed, but each load logs an encoding warning. Localization files without
    # a BOM are not loaded at all, so all text output is written with utf-8-sig.
    (out / "common" / "scripted_triggers" / "sg_law_availability.txt").write_text(
        emit_availability(groups, laws), encoding="utf-8-sig"
    )
    (out / "common" / "script_values" / "sg_law_scores.txt").write_text(
        emit_values(laws), encoding="utf-8-sig"
    )
    (out / "common" / "scripted_effects" / "sg_law_rank.txt").write_text(
        shift_effects() + emit_rank(laws), encoding="utf-8-sig"
    )
    (out / "common" / "scripted_effects" / "sg_law_actions.txt").write_text(
        emit_actions(laws), encoding="utf-8-sig"
    )
    (out / "common" / "scripted_guis").mkdir(parents=True, exist_ok=True)
    (out / "common" / "scripted_guis" / "sg_law_sguis.txt").write_text(
        emit_sguis(laws), encoding="utf-8-sig"
    )
    (out / "localization" / "english" / "sg_generated_l_english.yml").write_text(
        emit_loc(laws, "english"), encoding="utf-8-sig"
    )
    (out / "localization" / "braz_por" / "sg_generated_l_braz_por.yml").write_text(
        emit_loc(laws, "braz_por"), encoding="utf-8-sig"
    )
    (out / "data" / "law_ids.json").write_text(
        json.dumps(dict(sorted(law_ids.items())), indent=1, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (out / "data" / "law_data.json").write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "game": str(game),
                "groups": groups,
                "laws": laws,
            },
            indent=1,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(
        f"Wrote {len(laws)} laws across {len(groups)} groups "
        f"from {game} (schema {SCHEMA_VERSION})."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
