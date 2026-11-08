# Phase log

## Phase 0 — discovery

- Located Victoria 3 1.15.0 (Ivan-Chai) and the active Hydra/Wine user-data
  directory.
- Confirmed the live save and the active mod list.
- Inventoried 148 laws across 26 law groups and 298 modifier keys.
- Confirmed the 1.15 script mechanisms used by the mod.
- Studied the working 1.15 Economy Advisor mod for JE, scripted GUI, script
  value and localization patterns.

## Phase 1 — data design

- Decided to generate availability triggers, score values and ranking effects
  from the real vanilla law files instead of hand-writing them.
- Decided on one always-present journal entry, gated by `sg_enabled`, with
  monthly reassessment through the JE pulse.
- Decided on a small theme code system for localized benefit/risk/focus text,
  while showing real law effects through `GetEffectDesc` tooltips.
- Decided to store both the law type (for the GUI) and the numeric index (for
  logic) in country variables.

## Phase 2 — implementation

- Integrated the Clausewitz parser as `tools/pdx_parse.py`.
- Wrote `tools/build_law_data.py`:
  - parses all 148 laws and 26 groups;
  - generates availability triggers from `is_visible`, `can_enact`, group
    `enable`, group `change_allowed_trigger`, `unlocking_laws`,
    `unlocking_technologies`, `requires_law_or` and `disallowing_laws`;
  - scores real modifiers and writes benefit/risk/politics/score values;
  - writes the top-three ranking effect and enact/ignore effects;
  - writes generated English and Brazilian Portuguese localization and
    `data/law_data.json`.
- Wrote `tools/build_gui.py` and generated the journal-entry widget.
- Wrote the hand-authored runtime layer:
  - `je_sg_law_advisor`;
  - lifecycle, ignore and diagnostics effects;
  - shared triggers;
  - scripted GUIs for refresh, disable, enact, ignore, clear and diagnostics;
  - enable/disable decisions;
  - additive on-actions for game start and monthly initialization;
  - English and Brazilian Portuguese UI localization.
- Wrote `docs/AI_CONTEXT.md` and this log.

Static checks already run:

- braces balanced in every `common/*.txt` and `gui/*.gui`;
- every `law_type:` reference exists in the vanilla law files;
- every `has_technology_researched` reference exists in vanilla technology
  files;
- every generated/called `sg_*` name resolves to a definition;
- every scripted GUI named by the widget exists;
- every static localization key used by the widget exists in English;
- no duplicate top-level script blocks.

## Phase 3 — Sourcery review fixes

Addressed all 11 findings on PR #1:

- replaced positional law indexes with stable numeric ids in
  `data/law_ids.json`, preserved across list changes;
- added schema 2 migration that discards old positional state;
- generated one Enact and one Ignore button per law, so a click is bound to the
  law displayed and cannot be retargeted by a rerank;
- always reranked after an enact attempt, including a failed availability guard;
- selected benefit/risk themes from actual modifier contributions, with neutral
  themes for laws that have no measurable effect (`law_no_schools`, etc.);
- applied situational bonuses only when the law's real effects support them;
- scored all five tax brackets (average per key);
- replaced the hardcoded game path with `--game`, `VICTORIA3_GAME` and
  Steam/Hydra/manual-install discovery;
- added the launcher-facing `Smart Government Advisor.mod` and
  `tools/install_mod.py`;
- switched all widget localization keys to lowercase;
- rendered the numeric benefit score in each row;
- removed the law-type-variable path: the GUI selects per-law localization keys
  by stable id and calls `GetLawType('law_x')` in localization.

Static checks after regeneration: balanced braces, all law and technology
references exist, every `sg_*` call resolves, every GUI SGUI exists, every
static localization key exists, no duplicate keys or top-level blocks.

## Phase 4 — hardening, install and runtime test

Tooling:

- added `tools/validate.py`; it passes on the current generated tree;
- added `tools/install_mod.py` and the launcher-facing
  `Smart Government Advisor.mod`.

Extra hardening after the review:

- risk themes now use only positive risk contributions, so a law that reduces
  radicalism cannot show a radicalism warning;
- the generic risk sentence no longer claims local-autonomy tension for
  unrelated effects;
- ranking writes sentinel top ids (`0`) instead of removing them, and row
  visibility requires `id > 0`, so the widget never reads a missing variable
  when there are no recommendations;
- README and AI context were updated for `validate.py`, `install_mod.py` and
  the removal of law-type variables.

Installation performed:

- installed to
  `.../Documents/Paradox Interactive/Victoria 3/mod/Smart Government Advisor`
  and wrote `.../mod/Smart Government Advisor.mod`;
- created a separate test save copy:
  `save games/haiti_1836_06_30_SG_TEST.v3`;
- `content_load.json` was **not** edited; the mod is installed but inactive.

## Phase 5 — in-game runtime test fixes

- Fixed overlapping row text: replaced `GreaterThan_int32`/`LessThan_int32`
  with `EqualTo_int32` in `tools/build_gui.py` to prevent `FetchData` errors in
  the Clausewitz GUI engine which previously caused all 148 laws to render
  simultaneously.
- Fixed theme selector mapping: `EqualTo_int32` now covers the generated
  1..N values and falls back to the explicit zero-indexed localization key,
  so the initial value `0` no longer displays theme 1.
- Fixed journal entry disable lifecycle: `je_sg_law_advisor` uses
  `disable_evaluation` alongside its invalid outcome, removing the inactive
  entry after disable so the enable decision can create a fresh active entry.
- Fixed missing localization keys: added `je_sg_law_advisor`,
  `je_sg_law_advisor_reason` and `sg_disabled_desc` in English and Brazilian
  Portuguese.
- Re-validated with `tools/validate.py` (0 errors) and reinstalled via
  `tools/install_mod.py --force`.

## Phase 6 — startup runtime check

- Reinstalled the current branch into the Hydra/Wine user-data directory; the
  previously installed copy was stale and still contained the old
  `GreaterThan_int32`/`LessThan_int32` GUI expressions.
- Started `binaries/victoria3.exe` with the known Wine prefix and
  `-debug_mode`. The process reached normal GUI initialization and produced no
  advisor script, localization, or GUI parse errors.
- Found one real installation issue: the game logged a missing
  `.metadata/metadata.json` for the local mod. Added the same minimal metadata
  structure used by the other installed local mods.
- The test save copy remains separate:
  `save games/haiti_1836_06_30_SG_TEST.v3`.
- The environment does not provide reliable graphical control for loading that
  save and clicking the journal actions, so enact/ignore/disable/re-enable
  behavior remains unverified interactively.

## Phase 7 — advisor status UX

- Recorded the game month and year at the shared ranking refresh point, so both
  monthly reassessments and the manual refresh button update the displayed
  timestamp.
- Added a player-facing last-refresh line to the journal widget.
- Reworded the empty state to explicitly say that no available law can be
  recommended and explain the active, blocked and ignored cases.
- Follow-up review fixes initialize missing refresh date variables for older
  enabled saves, keep the refresh assignments in `tools/build_law_data.py`, and
  normalize localization indentation.
