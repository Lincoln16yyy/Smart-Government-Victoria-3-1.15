#!/usr/bin/env python3
"""Generate the Smart Government Advisor's research recommendation data.

Reads Victoria 3 technology definitions (common/technology/technologies/*.txt),
scores each one from its real modifier effects, and writes a JSON snapshot
plus the generated scripted artifacts needed by the research advisor widget.

Usage:
    python3 tools/build_research_data.py
    python3 tools/build_research_data.py --game "/path/to/Victoria 3/game" --out .

The generator is intentionally parallel to tools/build_law_data.py: the same
parser helpers, the same scoring families where the game shares them, and the
same deliberate posture that the advisor must never force a recommendation.

Important scope note:
    This snapshot currently lives in data/tech_data.json (human-readable dump)
    and is regenerated from the game files when the generator is pointed at a
    Victoria 3 install. The game itself does not ship a runtime value for
    "research speed", so the advisor does not try to model how fast a tech
    would finish. It only ranks technologies by the benefit they would add to
    the country if completed, which is the stuff the modifier blocks actually
    describe.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pdx_parse import parse, strip_comments  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TECH_DATA_FILE = ROOT / "data" / "tech_data.json"
SCHEMA_VERSION = 1

# Technologies the game marks as unavailable to research. Today that list is
# tiny (one tech), but we keep it explicit so the snapshot is honest about
# what the advisor may even consider.
CANNOT_RESEARCH_FIELD = "can_research"

# Minimum improvement in expected country benefit before a tech beats the
# current research or the already-researched one that is closest to it. The
# point is the same one used for laws: do not fill the top 3 with sidegrades.
MIN_IMPROVEMENT = 5.0


# ---------------------------------------------------------------------------
# Parsing helpers (mirrors build_law_data.py)
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
    pattern = rf"\b{re.escape(field)}\s*=\s*\{{"
    match = re.search(pattern, body)
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
    return [
        (key, str(value))
        for key, op, value in parse(strip_comments(raw))
        if op == "=" and isinstance(value, str)
    ]


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
# Technology scoring
# ---------------------------------------------------------------------------

TECHNOLOGY_DIRS = ("common/technology", "common/technology/technologies")


# Reuse the law scorer's compiled rule tables where they still describe the same
# game effects. The research snapshot is not the place to redefine scoring; that
# belongs with the rest of the advisor and should stay in one place.
from build_law_data import (
    COMPILED_BENEFIT,
    COMPILED_RISK,
    BENEFIT_THEME_RULES,
    BENEFIT_NEUTRAL_THEME,
    BENEFIT_GENERIC_THEME,
    RISK_NEUTRAL_THEME,
    FOCUS_BY_GROUP,
    choose_benefit_theme,
    choose_risk_theme,
    choose_focus,
    match_rule,
)


def tech_candidates_dir(game: Path) -> Path:
    for sub in TECHNOLOGY_DIRS:
        candidate = game / sub
        if (candidate / "10_production.txt").is_file():
            return candidate
    raise SystemExit(
        f"Could not find Victoria 3 technology folder under {game}. "
        "Expected common/technology/technologies/ or common/technology/."
    )


def read_technologies(game: Path) -> list[dict]:
    """Return one dict per technology definition, in file order."""
    tech_dir = tech_candidates_dir(game)
    out: list[dict] = []
    for path in sorted(tech_dir.glob("*.txt")):
        for name, body in top_level_blocks(path.read_text(encoding="utf-8-sig")):
            if name in ("tech_group",):
                continue
            modifier_block = field_block(body, "modifier")
            pairs = flat_pairs(modifier_block)
            out.append(
                {
                    "name": name,
                    "file": path.name,
                    "category": field_scalar(body, "category") or "unknown",
                    "can_research": (field_scalar(body, CANNOT_RESEARCH_FIELD) or "yes").lower()
                    != "no",
                    "ai_weight": field_scalar(body, "ai_weight"),
                    "unlocking_technologies": list_values(body, "unlocking_technologies"),
                    "modifier": pairs,
                }
            )
    return out


def score_technology(pairs: list[tuple[str, str]]) -> tuple[float, float, list[dict]]:
    """Return (benefit, risk, annotated).

    Reuses the same rule tables the law advisor uses where the effects overlap.
    A tech's modifier block is just a list of game effects, and many of them are
    identical in shape to a law modifier. The shape here is intentionally the
    same as build_law_data.score_modifiers so the two advisors stay comparable.
    """
    benefit_total, risk_total, annotated = 0.0, 0.0, []
    for key, value in pairs:
        number = numeric(value)
        benefit = match_rule(COMPILED_BENEFIT, key)
        risk = match_rule(COMPILED_RISK, key)
        b_contrib = max(-20.0, min(20.0, number * benefit))
        r_contrib = max(-20.0, min(20.0, number * risk))
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


def choose_technology_theme(annotated: list[dict]) -> int:
    """Describe the tech's real benefit, or fall back to neutral.

    Mirrors the law advisor's posture: if a tech has no positive measurable
    effect, the generic text should not claim a real bonus.
    """
    positive = [item["key"] for item in annotated if item["benefit"] > 0]
    if not positive:
        return BENEFIT_NEUTRAL_THEME
    joined = " ".join(positive)
    for pattern, theme in BENEFIT_THEME_RULES:
        if re.search(pattern, joined):
            return theme
    return BENEFIT_GENERIC_THEME


def choose_technology_focus(category: str) -> int:
    return {
        "production": 2,
        "military": 4,
        "society": 1,
    }.get(category, 1)


# ---------------------------------------------------------------------------
# Snapshot output (the "HTML-like" structured file the user asked for)
# ---------------------------------------------------------------------------

SNAPSHOT_FIELDS = [
    "name",
    "file",
    "category",
    "can_research",
    "ai_weight",
    "modifier",
    "unlocking_technologies",
    "benefit",
    "risk",
    "annotated",
]


def write_snapshot_deprecated(technologies: list[dict], out: Path) -> None:
    """Old snapshot path that used SNAPSHOT_FIELDS directly; removed because the
    first stable snapshot used a hardcoded field list and the dedupe pass needed
    the canonical view below. Retained only if a later fix reintroduces a
    field-based snapshot."""
    current = _by_name(technologies)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "game": str(game_resolve()),
                "technologies": [
                    {k: t[k] for k in SNAPSHOT_FIELDS}
                    for t in current
                ],
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(current)} technologies to {out} (by-name snapshot).")


def _by_name(technologies: list[dict]) -> list[dict]:
    """Keep one technology per name, preferring the entry that includes a
    modifier, and among those, the entry with the most modifiers."""
    grouped: dict[str, list[dict]] = {}
    for t in technologies:
        grouped.setdefault(t["name"], []).append(t)
    result: list[dict] = []
    for name in dict.fromkeys(t["name"] for t in technologies):
        candidates = grouped[name]
        if len(candidates) == 1:
            result.append({
                "name": name,
                "file": candidates[0]["file"],
                "category": candidates[0]["category"],
                "can_research": candidates[0]["can_research"],
                "ai_weight": candidates[0]["ai_weight"],
                "unlocking_technologies": candidates[0]["unlocking_technologies"],
                "modifier": candidates[0]["modifier"],
            })
            continue
        with_mod = [c for c in candidates if c["modifier"]]
        chosen = (with_mod[0] if with_mod else candidates[0])
        if with_mod:
            chosen = max(with_mod, key=lambda c: len(c["modifier"]))
        result.append({
            "name": name,
            "file": chosen["file"],
            "category": chosen["category"],
            "can_research": chosen["can_research"],
            "ai_weight": chosen["ai_weight"],
            "unlocking_technologies": chosen["unlocking_technologies"],
            "modifier": chosen["modifier"],
        })
    return result


def write_snapshot(technologies: list[dict], out: Path) -> None:
    """Human-readable JSON snapshot, indented, with computed scores inline."""
    formative = _by_name(technologies)
    snapshot: list[dict] = []
    for t in formative:
        benefit, risk, annotated = score_technology(t["modifier"])
        record: dict[str, object] = {
            "name": t["name"],
            "file": t["file"],
            "category": t["category"],
            "can_research": t["can_research"],
            "ai_weight": t["ai_weight"],
            "modifier": t["modifier"],
            "unlocking_technologies": t["unlocking_technologies"],
            "benefit": round(benefit, 2),
            "risk": round(risk, 2),
            "annotated": [
                {
                    "key": item["key"],
                    "value": item["value"],
                    "benefit": item["benefit"],
                    "risk": item["risk"],
                }
                for item in annotated
            ],
        }
        snapshot.append(record)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "game": str(game_resolve()),
                "technologies": snapshot,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(snapshot)} technologies to {out}.")


# ---------------------------------------------------------------------------
# Generated scripted artifacts (intention, no runtime claim)
# ---------------------------------------------------------------------------

def game_resolve() -> Path:
    "name",
    "file",
    "category",
    "can_research",
    "ai_weight",
    "modifier",
    "unlocking_technologies",
    "benefit",
    "risk",
    "annotated",
]


def write_snapshot(technologies: list[dict], out: Path) -> None:
    """Human-readable JSON snapshot, indented, with computed scores inline."""
    snapshot = []
    for t in technologies:
        benefit, risk, annotated = score_technology(t["modifier"])
        record = {k: t[k] for k in ("name", "file", "category", "can_research", "ai_weight", "modifier", "unlocking_technologies")}
        record["benefit"] = round(benefit, 2)
        record["risk"] = round(risk, 2)
        record["annotated"] = [
            {k: v for k, v in item.items() if k != "value"} | {"value": item["value"]}
            for item in annotated
        ]
        snapshot.append(record)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "game": str(game_resolve()),
                "technologies": snapshot,
            },
            indent=1,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(snapshot)} technologies to {out}.")


# ---------------------------------------------------------------------------
# Generated scripted artifacts (intention, no runtime claim)
# ---------------------------------------------------------------------------

def game_resolve() -> Path:
    """Return the game folder used by the last build, for embedding in JSON."""
    return Path(__file__).resolve().parent.parent / "game"
    """Return the game folder used by the last build, for embedding in JSON."""
    return Path(__file__).resolve().parent.parent / "game"
    """Return the game folder used by the last build, for embedding in JSON."""
    return Path(__file__).resolve().parent.parent / "game"
    """Return the game folder used by the last build, for embedding in JSON."""
    return Path(__file__).resolve().parent.parent / "game"


def emit_research_rank(technologies: list[dict]) -> str:
    """Intentional skeleton of what the research rank effect would look like.

    The generated file is not yet wired into the widget; it exists so the next
    step has a concrete target that parallels sg_law_rank.txt. The ranking
    logic here mirrors the law case: initialize sentinel slots, evaluate every
    technology, store the top 3, and keep the same opposition field shape so
    the advisor can reuse the same warning surface later if it makes sense for
    research.

    This skeleton is deliberately incomplete: it still uses the tech's name as
    the identifier and does not yet emit the per-technology scripted values or
    availability triggers. Follow-up work should replace tech names with stable
    ids and mirror the law advisor's store_block / shift_effects pattern.
    """
    out = ["# Generated by tools/build_research_data.py - do not edit by hand.", ""]
    out.append("sg_rank_research = {")
    out.append("\tsg_migrate_schema = yes")
    out.append("\tset_variable = { name = sg_last_research_refresh value = year }")
    out.append(f"\tset_variable = {{ name = sg_last_research_evaluated value = {len(technologies)} }}")
    for slot in (1, 2, 3):
        for field in (
            "id",
            "score",
            "benefit",
            "risk",
            "focus",
            "opposition",
        ):
            out.append(f"\tremove_variable = sg_top_{slot}_{field}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_id value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_benefit value = 17 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_risk value = 13 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_focus value = 1 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_opposition value = 0 }}")
        out.append(f"\tset_variable = {{ name = sg_top_{slot}_score value = -1000 }}")
    out.append("")
    for tech in technologies:
        if not tech["can_research"]:
            continue
        lid = tech["name"]
        benefit, risk, annotated = score_technology(tech["modifier"])
        theme = choose_technology_theme(annotated)
        focus = choose_technology_focus(tech["category"])
        score = max(0.0, min(200.0, 10 + benefit - risk * 0.45))
        out.append(f"\tif = {{")
        out.append(f"\t\tlimit = {{ sg_research_available_{lid} = yes }}")
        out.append(f"\t\tchange_variable = {{ name = sg_last_research_available add = 1 }}")
        out.append("\t\tif = {")
        out.append(f"\t\t\tlimit = {{ sg_research_merit_{lid} >= sg_research_upgrade_floor_{tech['category']} }}")
        out.append(f"\t\t\tif = {{ limit = {{ sg_research_score_{lid} > var:sg_top_1_score }} }}")
        out.append(f"\t\t\t\tshift_top_1 = yes")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_id value = {tech.get('sid', 0)} }}")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_score value = sg_research_score_{lid} }}")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_benefit value = {theme} }}")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_risk value = {RISK_NEUTRAL_THEME} }}")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_focus value = {focus} }}")
        out.append(f"\t\t\t\tset_variable = {{ name = sg_top_1_opposition value = sg_research_powerful_opposition_{lid} }}")
        out.append(f"\t\t\t}}")
        out.append("\t\t}")
        out.append("\t}")
    out.append("}")
    out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

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

    game = Path(args.game) if args.game else Path(__file__).resolve().parent.parent / "game"
    out = Path(args.out)

    technologies = read_technologies(game)
    if not technologies:
        print(f"No technologies parsed under {game}; check --game", file=sys.stderr)
        return 1

    # First persist the readable JSON snapshot the user asked for. Later
    # steps will add the generated scripted artifacts on top of this.
    write_snapshot(technologies, out / "data" / "tech_data.json")

    # Placeholder for the generated scripted artifacts that the advisor widget
    # will eventually read. Keeping this separate from the snapshot makes the
    # generator easier to extend without rewriting the JSON write path.
    research_dir = out / "common" / "scripted_effects"
    research_dir.mkdir(parents=True, exist_ok=True)
    research_rank_path = research_dir / "sg_research_rank.txt"
    research_rank_path.write_text(emit_research_rank(technologies), encoding="utf-8-sig")
    print(
        f"Parsed {len(technologies)} technologies from {game} "
        f"(schema {SCHEMA_VERSION}); wrote {research_rank_path}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
