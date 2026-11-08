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

## Phase 3 — validation and runtime test (next)

- Add `tools/validate.py` and `tools/install_mod.py`.
- Run the validator.
- Back up `content_load.json`, install to the real mod folder, copy a save.
- Load the copy and check `error.log`.
- Test enable, monthly reassessment, enact, ignore, clear, disable and
  re-enable.
- Fix runtime issues, especially `Var(...).GetLawType`, `law_stance` and
  `law_enactment_stance`.
- Write install/test/disable/diagnostics/compatibility docs.
- Commit on a branch, open a PR, address Sourcery review, merge to `main`.
