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

## Phase 8 — interactive action test preparation

- Rechecked Refresh, Enact, Ignore, Clear ignored, Disable and Re-enable across
  their scripted GUIs, effects, localization and journal-entry lifecycle.
- Re-ran the GUI generator, static validator, Python compilation and whitespace
  checks after the PR #4 merge.
- Confirmed the separate `haiti_1836_06_30_SG_TEST.v3` save and installed mod
  are present in the Hydra/Wine user-data directory.
- Added `docs/MANUAL_RUNTIME_TEST.md` with a reproducible action checklist,
  expected outcomes, backup/install commands and log checks.
- Startup/log inspection found no advisor-specific errors; the environment still
  cannot drive reliable in-game clicks, so interactive behavior remains pending
  a desktop-driven test.

## Phase 9 — ranking-cycle diagnostics

- Added generated ranking counters for laws checked, available, ignored,
  eligible and displayed.
- Reset the counters at the start of every ranking pass and remove them during
  disable, preventing stale status after lifecycle changes.
- Added a bilingual status line to the journal widget and expanded the
  diagnostics action text to point to the visible counters.
- Regenerated the 148-law output and passed static validation, Python
  compilation and whitespace checks.

## Phase 10 — recommendation explanations

- Added a visible per-row decomposition of the ranking formula:
  `benefit + government support - half of risk`.
- Clarified in English and Brazilian Portuguese that benefit/risk themes
  summarize measurable modifier families and that the law tooltip is the
  authoritative source for exact effects and requirements.
- Replaced the generic positive-benefit sentence with a neutral description of
  measurable score input, avoiding an unsupported claim about state capacity.

## Phase 11 — GUI visibility stabilization

- Reproduced the reported overlap against the installed build and found
  `FetchData failed` entries for direct `EqualTo_int32` comparisons against
  `JournalEntry.GetCountry.MakeScope.Var(...).GetValue`.
- Replaced direct GUI variable comparisons with generated country-scope
  visibility SGUIs, one per recommendation slot and law.
- Rendered law-specific benefit and risk explanations only inside the matching
  visible branch, removing the failing dynamic theme selector.
- Regenerated and installed the mod; `validate.py`, the 14-test regression
  suite, `py_compile` and `git diff --check` pass. The executable starts under
  Wine without new advisor/GUI/localization matches in the logs.
- Interactive save loading and clicks remain blocked by the lack of reliable
  graphical control in this environment; the repeatable checklist remains in
  `docs/MANUAL_RUNTIME_TEST.md`.

## Phase 12 — layout stabilization and review fixes

- Reworked each recommendation into a vertical card with explicit minimum and
  maximum heights, separated header, fixed-width metric boxes, bounded
  explanation panel and isolated action buttons.
- Restored the per-law focus theme inside the matching law branch without
  reintroducing direct variable comparisons or dynamic selector chains.
- Added regression coverage for every slot and every law: each header,
  explanation and action branch must reference its matching visibility SGUI, and
  each generated SGUI must compare the correct stable id.
- Regenerated and installed the visual layout; static validation, 15 tests,
  Python compilation and whitespace checks pass. Final visual confirmation
  still requires opening the test save in the game.

## Phase 13 — viability-aware recommendations

- Compared generated availability with vanilla legal requirements and the
  politics panel's current enactment state. The reported laws were legally
  visible but the panel showed 0% success, so the defect was a combination of
  missing feasibility filtering and benefit-only ranking pressure, not a
  missing `is_visible` or `can_enact` requirement in those three definitions.
- Added the vanilla `LAW_MIN_SUCCESS_CHANCE` gate (1%), excluded countries
  already enacting another law, and added the current
  `enactment_chance_for_law(law_type:...)` value as a bounded ranking factor.
- Stored and displayed the current estimated chance in each recommendation
  explanation; no success guarantee or enactment-process change was added.
- Added regression cases for Hindu Caste Enforced, Hindu Caste Codified and
  National Supremacy. Generators and all requested static checks pass; the
  remaining validation is the manual save/UI test.

## Phase 14 — interactive ignored laws management and powerful opposition risk

- Added individual restore buttons and visible rows for ignored laws in the
  journal entry widget, showing the law name, group, and a dedicated Restore
  action for each active ignored slot.
- Implemented `sg_restore_ignored_1`, `sg_restore_ignored_2`, and
  `sg_restore_ignored_3` effects that compact the remaining ignored variables
  and rerank immediately.
- Generated `sg_ignored_{slot}_law_{lid}_visible_sgui` to ensure stable,
  flicker-free display of ignored laws without direct GUI variable comparison.
- Added situational risk penalty (`+12`) to laws that strongly alienate a
  powerful interest group (`is_powerful = yes` with `strongly_disapprove`),
  mitigating revolution and insurrection risk in recommended laws.
- Added unit tests covering individual restore SGUIs, ignored laws rendering,
  and powerful opposition risk scoring in `tests/test_advisor_generation.py`.
- Re-ran generators, passed all 18 regression tests, static validation and
  reinstalled the mod via `tools/install_mod.py --force`.

## Phase 15 — one recommendation per law group and GUI log cleanup

- Found 2,300 `Property 'autoresize' not handled` errors in the live 1.15
  `error.log`, all pointing at generated plain `widget` wrappers. `autoresize`
  is valid on textboxes only in this version. Removed it from the four wrapper
  generators; the engine was already ignoring the property, so layout is
  unchanged and the log noise disappears.
- Added `tools/validate.py` and regression coverage that reject
  `autoresize` directly on a `widget`, so the generator cannot reintroduce it.
- The ranking could show three mutually exclusive laws of the same group in the
  top three (the static top ten is dominated by citizenship variants). Added
  generated `sg_law_candidate_<law>` and `sg_law_group_leader_<law>` triggers in
  `common/scripted_triggers/sg_law_groups.txt`. Only the highest-scored
  available, non-ignored law of each group can enter the top three; exact ties
  go to the lower stable id. Ignoring a group leader lets the next-best law of
  that group compete.
- Added the `sg_last_rank_group_filtered` diagnostic counter to the ranking
  cycle, the journal status line and the disable cleanup.
- Updated English and Brazilian Portuguese header text to explain the
  one-per-group rule.
- Regenerated 148 laws and 26 groups; 22 regression tests, `validate.py`,
  `py_compile` and `git diff --check` pass. Reinstalled the mod with
  `tools/install_mod.py --force`.
- Launched the game under Wine and read the rotating `error*.log` files. The
  startup exposed further issues that static checks could not see:
  - `MakeScope.HasVariable(...)` is not a GUI data function and produced a
    malformed-token error. The diagnostic line now uses the generated-pattern
    SGUI `sg_rank_diagnostic_visible_sgui`.
  - Hand-written localization files had no UTF-8 BOM and were not loaded, so
    the journal entry reported an unknown `sg_je_activation_tt` key and every
    hand-written GUI string was unlocalized. All `.yml`, `.txt` and `.gui`
    files are now written or saved with a BOM, and `validate.py` rejects a file
    without one.
  - `sg_law_scores.txt` used `any_scope_interest_group` and
    `every_scope_interest_group`; 1.15 names the lists `any_interest_group` and
    `every_interest_group`. It also compared `radical_fraction > X` directly,
    but `radical_fraction` is a block trigger. Both were fixed, removing 662
    load-time errors.
  - `define:LAW_MIN_SUCCESS_CHANCE` was missing its namespace; 1.15 requires
    `define:NPolitics|LAW_MIN_SUCCESS_CHANCE`. This was the last load-time
    error (296 occurrences across the 148 availability triggers).
- Final runtime check: the mod produced zero errors in the new `error*.log`
  files (no `autoresize`, `HasVariable`, unlocalized `sg_` key, missing-BOM or
  parse error). Nine benign "variable never set" warnings remain for the
  schema-1 migration variables and the optional `sg_debug` switch.
- 25 regression tests, `validate.py`, `py_compile` and `git diff --check` pass.
  The mod was reinstalled before the final launch.
