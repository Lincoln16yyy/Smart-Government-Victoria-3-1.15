#!/usr/bin/env python3
"""Compile the contextual research policy against the installed technology tree."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from zlib import crc32

from build_law_data import resolve_game_path
from build_research_gui import SLOTS, write_localizations
from pdx_parse import parse
from research_policy import CONTEXTS, POLICY

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path("data/tech_advisor_candidates.json")
EFFECTS = Path("common/scripted_effects/sg_research_rank.txt")
TRIGGERS = Path("common/scripted_triggers/sg_research_candidates.txt")
SGUIS = Path("common/scripted_guis/sg_research_sguis.txt")


def read_technologies(game: Path) -> dict:
    technologies = {}
    for path in sorted((game / "common/technology/technologies").glob("*.txt")):
        for name, _, fields in parse(path.read_text(encoding="utf-8-sig")):
            if not isinstance(fields, list):
                raise ValueError(f"Expected a technology definition for {name}")
            props = {key: val for key, _, val in fields}
            prerequisites = [key for key, _, _ in props.get("unlocking_technologies", [])]
            if name in technologies:
                raise ValueError(f"Duplicate technology {name}")
            technologies[name] = {
                "name": name,
                "category": props["category"],
                "can_research": props.get("can_research", "yes") == "yes",
                "prerequisites": prerequisites,
            }
    if not technologies:
        raise ValueError(f"No technology definitions found under {game}")
    return technologies


def candidates(technologies: dict) -> list[dict]:
    records = []
    for name, context, score, _pt, _en in POLICY:
        tech = technologies[name]
        if not tech["can_research"] or not all(p in technologies for p in tech["prerequisites"]):
            raise ValueError(f"{name} has unsupported availability rules")
        records.append({
            **tech,
            "id": crc32(name.encode()) & 0x7FFFFFFF,
            "context": context,
            "score": score,
        })
    if len(records) != len({tech["id"] for tech in records}) or any(not t["id"] for t in records):
        raise ValueError("Candidate IDs must be positive and unique")
    return records


def trigger_name(tech: dict) -> str:
    return f"sg_research_available_{tech['name'].replace('-', '_')}"


def emit_triggers(records: list[dict]) -> str:
    blocks = []
    for tech in records:
        name = tech["name"]
        tests = [
            f"NOT = {{ has_technology_researched = {name} }}",
            f"NOT = {{ is_researching_technology = {name} }}",
            *(f"has_technology_researched = {p}" for p in tech["prerequisites"]),
        ]
        blocks.append(f"{trigger_name(tech)} = {{\n\t" + "\n\t".join(tests) + "\n}")
    return "\n\n".join(blocks) + "\n"


def slot_field(slot: int, field: str) -> str:
    return f"sg_research_{slot}_{field}"


def assign(slot: int, source: str) -> list[str]:
    return [
        f"set_variable = {{ name = {slot_field(slot, field)} value = var:{source}_{field} }}"
        for field in ("id", "score")
    ]


def emit_effects(records: list[dict]) -> str:
    lines = ["sg_research_rank = {", "\tif = {",
             "\t\tlimit = { is_player = yes has_variable = sg_enabled }"]
    for slot in SLOTS:
        for field in ("id", "score"):
            lines.append(f"\t\tset_variable = {{ name = {slot_field(slot, field)} value = 0 }}")
    for context in CONTEXTS:
        lines += [
            "\t\tif = {", f"\t\t\tlimit = {{ sg_research_{context} = yes }}",
        ]
        for tech in records:
            if tech["context"] != context:
                continue
            lines += [
                "\t\t\tif = {",
                f"\t\t\t\tlimit = {{ {trigger_name(tech)} = yes }}",
                f"\t\t\t\tset_variable = {{ name = sg_research_candidate_id value = {tech['id']} }}",
                "\t\t\t\tset_variable = { name = sg_research_candidate_score value = "
                f"{tech['score']} }}",
                "\t\t\t\tsg_research_insert = yes",
                "\t\t\t}",
            ]
        lines.append("\t\t}")
    lines += ["\t\tremove_variable = sg_research_candidate_id",
              "\t\tremove_variable = sg_research_candidate_score", "\t}", "}", "",
              "sg_research_insert = {"]
    for slot in SLOTS:
        branch = "if" if slot == 1 else "else_if"
        lines += [
            f"\t{branch} = {{",
            f"\t\tlimit = {{ var:sg_research_candidate_score > var:{slot_field(slot, 'score')} }}",
        ]
        for dest in reversed(SLOTS[slot:]):
            lines.extend("\t\t" + line for line in assign(dest, f"sg_research_{dest - 1}"))
        lines.extend("\t\t" + line for line in assign(slot, "sg_research_candidate"))
        lines.append("\t}")
    lines += ["}", "", "sg_research_clear = {"]
    for slot in SLOTS:
        lines.extend(f"\tremove_variable = {slot_field(slot, field)}" for field in ("id", "score"))
    return "\n".join([*lines, "}", ""])


def emit_sguis(records: list[dict]) -> str:
    blocks = ["""sg_research_visible_sgui = {
	scope = country
	is_shown = { is_player = yes has_variable = sg_enabled }
}

sg_research_refresh_sgui = {
	scope = country
	is_valid = { is_player = yes has_variable = sg_enabled }
	effect = { sg_research_rank = yes }
}

sg_research_active_sgui = {
	scope = country
	is_shown = { is_researching_technology = any }
}

sg_research_empty_sgui = {
	scope = country
	is_shown = {
		OR = {
			NOT = { has_variable = sg_research_1_id }
			var:sg_research_1_id = 0
		}
	}
}"""]
    for slot in SLOTS:
        field = slot_field(slot, "id")
        for tech in records:
            token = tech["name"].replace("-", "_")
            blocks.append(
                f"sg_research_{slot}_{token}_sgui = {{\n\tscope = country\n"
                f"\tis_shown = {{ has_variable = {field} var:{field} = {tech['id']} "
                f"{trigger_name(tech)} = yes }}\n}}"
            )
    return "\n\n".join(blocks) + "\n"


def write(out: Path, path: Path, body: str) -> None:
    target = out / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# Generated by tools/build_research_data.py.\n" + body, encoding="utf-8-sig")


def build(game: Path, out: Path) -> None:
    records = candidates(read_technologies(game))
    manifest = out / MANIFEST
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(records, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write(out, TRIGGERS, emit_triggers(records))
    write(out, EFFECTS, emit_effects(records))
    write(out, SGUIS, emit_sguis(records))
    write_localizations(out, records)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game")
    parser.add_argument("--out", type=Path, default=ROOT)
    args = parser.parse_args()
    build(resolve_game_path(args.game), args.out)
