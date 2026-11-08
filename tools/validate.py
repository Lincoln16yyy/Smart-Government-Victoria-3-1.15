#!/usr/bin/env python3
"""Static validation for the Smart Government Advisor.

Checks the generated and hand-written script without starting the game:
brace balance, law/technology references, scripted-name resolution, GUI SGUI
references, localization keys, duplicate top-level blocks, stable law ids and
the presence of the per-law name/tooltip keys used by the widget.

Usage:
    python3 tools/validate.py
    python3 tools/validate.py --game "/path/to/Victoria 3/game"
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_law_data import resolve_game_path  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


def brace_balance(path: Path) -> tuple[bool, int | str]:
    text = path.read_text(encoding="utf-8-sig")
    depth = 0
    in_string = False
    escaped = False
    i = 0
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
            elif ch == "#":
                while i < len(text) and text[i] != "\n":
                    i += 1
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth < 0:
                    return False, "negative"
        i += 1
    return depth == 0, depth


def top_level_names(text: str) -> set[str]:
    return set(re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", text, re.M))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", default=None)
    args = parser.parse_args()
    game = resolve_game_path(args.game)

    errors: list[str] = []
    warnings: list[str] = []

    common = list((ROOT / "common").rglob("*.txt"))
    gui_files = list((ROOT / "gui").rglob("*.gui"))
    for path in common + gui_files:
        ok, depth = brace_balance(path)
        if not ok:
            errors.append(f"unbalanced braces in {path} ({depth})")
        if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append(
                f"{path.relative_to(ROOT)} must be saved as UTF-8 with BOM "
                "(1.15 logs an encoding warning without it)"
            )

    texts = {str(path): path.read_text(encoding="utf-8-sig") for path in common}

    laws = set()
    for path in (game / "common" / "laws").glob("*.txt"):
        laws.update(re.findall(r"^(law_[A-Za-z0-9_]+)\s*=", path.read_text(encoding="utf-8-sig"), re.M))
    law_refs = set()
    for text in texts.values():
        law_refs.update(re.findall(r"law_type:([A-Za-z0-9_]+)", text))
    for missing in sorted(law_refs - laws):
        errors.append(f"unknown law_type reference: {missing}")

    technologies = set()
    for path in (game / "common" / "technology").rglob("*.txt"):
        technologies.update(top_level_names(path.read_text(encoding="utf-8-sig")))
    tech_refs = set()
    for text in texts.values():
        tech_refs.update(re.findall(r"has_technology_researched\s*=\s*([A-Za-z0-9_]+)", text))
    for missing in sorted(tech_refs - technologies):
        errors.append(f"unknown technology reference: {missing}")

    definitions = set()
    for text in texts.values():
        definitions.update(re.findall(r"^(sg_[A-Za-z0-9_]+)\s*=\s*\{", text, re.M))
    calls = set()
    for text in texts.values():
        calls.update(re.findall(r"\b(sg_[A-Za-z0-9_]+)\s*=\s*yes", text))
    for missing in sorted(calls - definitions):
        errors.append(f"undefined scripted call: {missing}")

    gui_path = ROOT / "gui" / "journal_entry_widgets" / "sg_law_advisor.gui"
    gui = gui_path.read_text(encoding="utf-8")
    gui_sguis = set(re.findall(r"GetScriptedGui\('([A-Za-z0-9_]+)'\)", gui))
    for missing in sorted(gui_sguis - definitions):
        errors.append(f"GUI references missing SGUI: {missing}")
    if "HasVariable(" in gui:
        errors.append(
            "GUI uses HasVariable(), which is not a data system function in 1.15; "
            "use a country-scope visibility SGUI instead"
        )

    define_refs = set()
    for text in texts.values():
        define_refs.update(re.findall(r"define:([A-Za-z0-9_|]+)", text))
    for ref in sorted(define_refs):
        if "|" not in ref:
            errors.append(
                f"define:{ref} is missing its namespace; 1.15 expects "
                "define:Namespace|Name (for example define:NPolitics|LAW_MIN_SUCCESS_CHANCE)"
            )

    values_text = texts.get(str(ROOT / "common" / "script_values" / "sg_law_scores.txt"), "")
    if "scope_interest_group" in values_text:
        errors.append(
            "sg_law_scores.txt uses *_scope_interest_group; 1.15 names the list "
            "any_interest_group / every_interest_group"
        )
    if "radical_fraction >" in values_text:
        errors.append(
            "sg_law_scores.txt compares radical_fraction directly; 1.15 requires "
            "radical_fraction = { value >= X }"
        )

    # 1.15 rejects `autoresize` on a plain widget ("Property 'autoresize' not
    # handled" in error.log) and spams the log once per generated branch. It is
    # a valid textbox property, so only direct children of a widget block are
    # checked here.
    gui_lines = gui.splitlines()
    for index, line in enumerate(gui_lines):
        if not re.match(r"^\s*widget\s*=\s*\{\s*$", line):
            continue
        indent = len(line) - len(line.lstrip("\t"))
        for child_index in range(index + 1, min(index + 8, len(gui_lines))):
            child = gui_lines[child_index]
            if not child.strip():
                continue
            child_indent = len(child) - len(child.lstrip("\t"))
            if child_indent <= indent:
                break
            if child_indent == indent + 1 and child.strip() == "autoresize = yes":
                errors.append(
                    f"{gui_path.relative_to(ROOT)}:{child_index + 1} sets autoresize "
                    "on a widget (1.15 supports it on textboxes only)"
                )
                break

    loc_keys: set[str] = set()
    for path in (ROOT / "localization").rglob("*.yml"):
        if not path.read_bytes().startswith(b"\xef\xbb\xbf"):
            errors.append(
                f"{path.relative_to(ROOT)} must be saved as UTF-8 with BOM "
                "(1.15 skips a localization file without it)"
            )
        loc_keys.update(
            re.findall(r"^\s*([A-Za-z0-9_]+):\d+", path.read_text(encoding="utf-8-sig"), re.M)
        )
    gui_keys = set(
        re.findall(r'(?:text|tooltip|raw_text)\s*=\s*"([A-Za-z0-9_]+)"', gui)
    )
    for missing in sorted(gui_keys - loc_keys):
        errors.append(f"GUI references missing localization key: {missing}")

    # The same key in different language files is expected. Only a duplicate
    # inside one language file is an error.
    for path in (ROOT / "localization").rglob("*.yml"):
        keys = re.findall(
            r"^\s*([A-Za-z0-9_]+):\d+",
            path.read_text(encoding="utf-8-sig"),
            re.M,
        )
        for key, count in collections.Counter(keys).items():
            if count > 1:
                errors.append(f"duplicate localization key in {path}: {key}")

    blocks: dict[str, list[str]] = collections.defaultdict(list)
    for path in common:
        for name in re.findall(r"^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*\{", texts[str(path)], re.M):
            blocks[name].append(str(path))
    for name, paths in blocks.items():
        if len(paths) > 1:
            errors.append(f"duplicate top-level block {name}: {paths}")

    data = json.loads((ROOT / "data" / "law_data.json").read_text(encoding="utf-8"))
    ids = json.loads((ROOT / "data" / "law_ids.json").read_text(encoding="utf-8"))
    if len(set(ids.values())) != len(ids):
        errors.append("data/law_ids.json contains duplicate numeric ids")
    generated_laws = {law["id"] for law in data["laws"]}
    # Ids of removed laws stay reserved on purpose, so the mapping may be a
    # superset of the current list.
    if not generated_laws <= set(ids):
        errors.append("data/law_ids.json is missing one or more generated laws")
    for law in data["laws"]:
        sid = law["sid"]
        if ids.get(law["id"]) != sid:
            errors.append(f"{law['id']} has inconsistent stable id")
        for key in (f"sg_law_name_{sid}", f"sg_law_group_{sid}", f"sg_law_tip_{sid}"):
            if key not in loc_keys:
                errors.append(f"missing generated localization key: {key}")
        for key in (
            f"sg_law_candidate_{law['id']}",
            f"sg_law_group_leader_{law['id']}",
        ):
            if key not in definitions:
                errors.append(f"missing generated group trigger: {key}")

    old_state = []
    for path, text in texts.items():
        for match in re.finditer(r"sg_top_[123]_(?:law|index)\b", text):
            line = text.count("\n", 0, match.start()) + 1
            line_text = text.splitlines()[line - 1].strip()
            if not line_text.startswith("remove_variable"):
                old_state.append(f"{path}:{line} {line_text}")
    for item in old_state:
        errors.append(f"old positional-state reference: {item}")

    if not (ROOT / "Smart Government Advisor.mod").is_file():
        errors.append("missing launcher descriptor: Smart Government Advisor.mod")

    if errors:
        print(f"{len(errors)} error(s):")
        for error in errors:
            print(f"  - {error}")
        return 1
    if warnings:
        for warning in warnings:
            print(f"warning: {warning}")
    print(
        f"OK: {len(generated_laws)} laws, {len(blocks)} top-level blocks, "
        f"{len(loc_keys)} localization keys checked."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
