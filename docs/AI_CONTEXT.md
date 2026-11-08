# Smart Government Advisor — AI context file

This file is the hand-off document for another AI or developer picking up this
repository. It records the design, the exact game/save paths on the original
machine, what is generated, what is hand-written, what has been verified, and
what still needs a runtime test.

Last updated: 2026-11-08 (phase 17: enactment pause state, legitimacy risk theme and powerful-opposition warning; schema 2).

---

## 1. Goal

Build a Victoria 3 **1.15** mod that recommends laws through a journal entry.
It must:

- only recommend and never auto-approve a law;
- use the normal law-enactment process (`start_enactment`), never a cheat or an
  instant approval, and never manipulate legitimacy, interest groups or the
  opposition;
- recommend top-three laws with score, benefits, risks and explanations;
- let the player enact, ignore, reanalyse, enable and disable;
- reassess periodically (monthly);
- extract **real** 1.15 law effects; never invent identifiers, triggers or
  modifiers;
- work in Brazilian Portuguese with English fallback;
- coexist with OGAS, Supply Chain Semi-Auto Builder, Auto-Apply PMs,
  Auto-Apply Automation PMs, Auto-Diplomacy, Auto-Recruit and Kuromi's AI;
- never edit original game files.

Absolute priority: the mod must load and work. A smaller mod that loads beats a
large mod with broken syntax.

---

## 2. Environment used during development

- Game install: `/home/lincoln-ii/Games/Victoria 3`
- Game version: `1.15.0 (Ivan-Chai)`, build
  `release/1.15.06338547985dbc271523e149f362a6fd93dc62975`
- Wine/Hydra prefix: `/home/lincoln-ii/.config/hydralauncher/wine-prefixes/529340`
- User data, mods, saves and logs:
  `/home/lincoln-ii/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3`
- `content_load.json` (active mod list) is in that user-data directory.
- Repository: `/home/lincoln-ii/Victoria3_mod`
- Remote: `https://github.com/Lincoln16yyy/Smart-Government-Victoria-3-1.15.git`

Do not kill a running game or edit `content_load.json` without a backup. Test
on a **copy** of a save, never on the player's only save.

---

## 3. Verified 1.15 mechanisms

These were checked against the game files and/or a working 1.15 reference mod
(Economy Advisor, workshop id 3778129206).

| Mechanism | Use in this mod |
| --- | --- |
| `start_enactment = law_type:law_x` | starts normal enactment |
| `enacting_any_law = yes` | blocks a second enactment |
| `is_enacting_law = law_type:x` | available but not used |
| `has_law_or_variant = law_type:x` | current-law and requirement checks |
| `law_stance = { law = law_type:x value >= approve }` | interest-group stance |
| `law_enactment_stance = { law = law_type:x value >= approve }` | ruler stance (character scope) |
| JE `widget = { gui = ... name = ... container = "custom_widget_container_3" }` | journal-entry UI |
| JE `on_monthly_pulse = { effect = { ... } }` | monthly reassessment |
| JE `is_shown_when_inactive`, `possible`, `disable_evaluation`, `can_deactivate` | lifecycle |
| `add_journal_entry = { type = je_x }` | create the entry |
| `has_inactive_journal_entry = je_x` | avoid duplicate creation |
| `debug_log = "..."` | diagnostics |
| `GetLawType('law_x')` in localization | law name, group and tooltips in the generated row lookups |
| `GetLawType('law_x').GetEffectDesc(GetPlayer.Self)` | real current effects |
| `GetLawType('law_x').GetBlockingRequirements(GetPlayer.Self)` | real blocking requirements |
| `GetLawType('law_x').GetGroup.GetName` | law group name |
| `GetScriptedGui('sg_enact_law_x_sgui')` | one button per law, cannot be retargeted by a rerank |
| `var:x ?= / =` and `set_variable value = var:y` | variable copying |
| On-actions with `on_actions = { dispatcher }` | additive, preserves vanilla |
| `SelectLocalization(bool, key, key)` and `LessThan_int32` | dynamic localized text in GUI |
| script value comparison in a trigger (both sides) | group-leader selection; vanilla uses `political_movement_radicalism >= india_independence_radicalism_threshold` |
| `autoresize = yes` is a textbox property, rejected on a plain `widget` | fixed in phase 15; `error.log` reported "Property 'autoresize' not handled" for 1,776 generated widget wrappers |
| `define:Namespace|Name` (for example `define:NPolitics|LAW_MIN_SUCCESS_CHANCE`) | availability gate; an un-namespaced define is rejected at load with "Invalid define, expected 'Namespace|Name'" |
| `any_interest_group` / `every_interest_group` in a script value | politics score and powerful-opposition risk; `any_scope_interest_group` and `every_scope_interest_group` are not valid list names in 1.15 |
| `radical_fraction = { value >= X }` | situational adjustments; it is a block trigger, not a comparable script value |
| UTF-8 BOM in every `.txt`, `.gui` and `.yml` | scripts log an encoding warning without it; localization files are not loaded without it |
| `HasVariable()` is not a GUI data function | direct use produced "Malformed token"; the diagnostic line uses `sg_rank_diagnostic_visible_sgui` instead |

Unverified at runtime (still marked as risk):

- `law_stance` inside `every_scope_interest_group` in a script value (vanilla
  uses it in interest-group triggers; script-value lists should work).
- `law_enactment_stance` on `ruler` in a country-scope script value.
- `GreaterThan_int32` / `LessThan_int32` exact-id visibility branches in this
  widget (the functions are used by vanilla GUI; the generated chain must be
  confirmed in `error.log`).

The old risk about law-type values in country variables was removed together
with that design: the GUI now looks laws up by stable numeric id and calls
`GetLawType('law_x')` inside localization.

If any of these fail, the fallback is documented in section 10.

---

## 4. Repository layout

Hand-written files:

```
descriptor.mod
common/journal_entries/sg_journal_entries.txt
common/scripted_effects/sg_effects.txt
common/scripted_triggers/sg_core_triggers.txt
common/scripted_guis/sg_scripted_guis.txt
common/decisions/sg_decisions.txt
common/on_actions/sg_on_actions.txt
localization/english/sg_l_english.yml
localization/braz_por/sg_l_braz_por.yml
tools/build_law_data.py
tools/build_gui.py
tools/pdx_parse.py
tools/install_mod.py
Smart Government Advisor.mod
docs/AI_CONTEXT.md
docs/PHASE_LOG.md
```

Generated files (do not edit by hand; rerun the tools):

```
common/scripted_triggers/sg_law_availability.txt
common/script_values/sg_law_scores.txt
common/scripted_effects/sg_law_rank.txt
common/scripted_effects/sg_law_actions.txt
common/scripted_guis/sg_law_sguis.txt
gui/journal_entry_widgets/sg_law_advisor.gui
localization/english/sg_generated_l_english.yml
localization/braz_por/sg_generated_l_braz_por.yml
data/law_data.json
data/law_ids.json
```

Build commands:

```bash
cd /home/lincoln-ii/Victoria3_mod
python3 tools/build_law_data.py
python3 tools/build_gui.py
```

`build_law_data.py` reads `common/laws/*.txt` and
`common/law_groups/*.txt` from the game install. Pass `--game` if the game is
somewhere else.

---

## 5. Runtime data flow

1. **Enable.** A new campaign gets `sg_initialize_country` from
   `on_game_started_after_lobby`. An existing save is enabled by the
   `sg_enable_smart_government` decision or automatically on the first monthly
   pulse if `sg_schema_version` does not exist. Disabling leaves
   `sg_schema_version` behind, so the advisor never silently re-enables.
2. **Journal entry.** `sg_ensure_journal_entry` initializes missing refresh
   date variables and adds `je_sg_law_advisor` if neither the active nor the
   inactive entry exists. The monthly dispatcher also initializes those
   variables for older saves that already have the advisor enabled.
3. **Evaluation.** `sg_rank_laws` first calls `sg_migrate_schema` (schema 1
   positional state is discarded), sets every top slot to `-1000`, then iterates
   all 148 laws. For each law it checks `sg_law_available_<law>` and the ignored
   list. An available, non-ignored law must also pass the upgrade gate:
   `sg_law_merit_<law> >= sg_law_upgrade_floor_<group>`, where the floor is the
   merit of the law currently in force in that group plus 5. The ranking is
   global (no one-per-group quota); a law that fails the gate is counted as
   "no real gain". A   passing law's **stable numeric law id**, score, benefit
   theme, risk theme, focus theme, benefit score, risk score, political
   score, enactment chance and powerful-opposition flag are stored in the top
   slots.
4. **Monthly.** The JE `on_monthly_pulse` calls `sg_monthly_update`, which
   ensures the entry exists and reruns `sg_rank_laws`.
5. **Enact.** Each row contains one Enact button per law, bound to
   `sg_enact_law_<law>_sgui` and visible only while `sg_top_N_id` equals that
   law. The effect re-checks `sg_law_available_<law>` and
   `NOT = { enacting_any_law = yes }`, runs `start_enactment = law_type:<law>`,
   then always reranks. A stale click therefore cannot target another law or
   leave a dead row on screen.
6. **Ignore.** Each row contains one Ignore button per law, bound to
   `sg_ignore_law_<law>_sgui`. It stores that law's stable id in the first free
   `sg_ignored_1..3` slot and reranks. `sg_clear_ignored` removes the three
   slots and reranks.
7. **Disable.** `sg_disable_country` removes all runtime variables. The JE's
   `disable_evaluation` makes the entry inactive and removes it.

The generated widget uses one country-scope visibility SGUI per slot and law
(`sg_top_<slot>_law_<law>_visible_sgui`). This is intentional: direct
`EqualTo_int32`/`Var(...).GetValue` expressions produced `FetchData failed` in
the live GUI and caused hidden law branches to overlap. The matching branch
renders the law-specific benefit and risk explanations directly.

### Stored country variables

Top slots (`N` = 1, 2, 3):

- `sg_top_N_id` — stable numeric law id from `data/law_ids.json`
- `sg_top_N_score` — final score
- `sg_top_N_benefit` — benefit theme code (1–17; 17 is neutral)
- `sg_top_N_risk` — risk theme code (1–13; 13 is neutral)
- `sg_top_N_focus` — focus code (1–6)
- `sg_top_N_benefit_score` — numeric benefit
- `sg_top_N_risk_score` — numeric risk
- `sg_top_N_politics` — numeric government support
- `sg_top_N_enactment_chance` — current estimated enactment chance, 0–100
- `sg_top_N_opposition` — 1 when a powerful interest group strongly
  disapproves of the recommended law, 0 otherwise; drives the visible warning

Other variables:

- `sg_enabled` — advisor is on
- `sg_schema_version` — schema marker (2; never removed on disable)
- `sg_ignored_1..3` — stable numeric law ids
- `sg_ignored_selected` — short-lived helper for the ignore effect
- `sg_last_refresh_year` / `sg_last_refresh_month` — game date recorded by
  every monthly or manual ranking refresh
- `sg_last_rank_evaluated` — total laws traversed by the generated ranking cycle
- `sg_last_rank_available` — laws passing availability before ignore filtering
- `sg_last_rank_ignored` — available laws excluded by the ignored list
- `sg_last_rank_upgrade_filtered` — available, non-ignored laws suppressed
  because their merit did not beat the current law of their group by 5 points
  (the old `sg_last_rank_group_filtered` name is removed on disable)
- `sg_last_rank_eligible` — available, non-ignored laws that passed the upgrade
  gate and reached score comparison
- `sg_last_ranked_count` — number of populated recommendation slots after ranking
- `sg_debug` — optional; enables lifecycle `debug_log` messages

---

## 6. Availability model

For every law, `tools/build_law_data.py` writes
`sg_law_available_<law_id>`. It contains:

- `NOT = { has_law_or_variant = law_type:<law> }` (do not recommend current law)
- `NOT = { enacting_any_law = yes }` (do not recommend while another law is
  in progress)
- the vanilla estimated enactment chance must be at least
  `define:LAW_MIN_SUCCESS_CHANCE` (the 1.15 minimum is 1%; a 0% law is not a
  viable recommendation)
- the law group's `enable` block
- the law group's `change_allowed_trigger`
- the law's `is_visible` block
- the law's `can_enact` block
- `disallowing_laws` as `NOT = { OR = { has_law_or_variant = ... } }`
- `unlocking_laws` as `OR = { has_law_or_variant = ... }`
- every `unlocking_technologies` as `has_technology_researched = <tech>`
- `requires_law_or` as `OR = { has_law_or_variant = ... }`

`scope:law` inside copied vanilla triggers is rewritten to the concrete
`law_type:<law>`.

### Current-law comparison

The ranking is global and has no one-per-group quota. Instead,
`sg_law_scores.txt` generates, for every law group,
`sg_law_current_merit_<group>` and `sg_law_upgrade_floor_<group>`:

- `sg_law_current_merit_<group>` adds the merit of the law that is active in the
  group. It uses `has_law = law_type:<law>` (not `has_law_or_variant`, which can
  match both a parent law and its variant and add two merits).
- `sg_law_upgrade_floor_<group>` is that current merit plus `MIN_IMPROVEMENT`
  (5 points).

An available, non-ignored law enters the top three only when its
`sg_law_merit_<law>` reaches the floor of its group. If no law reaches it, the
list stays empty and the journal shows the "already in force" message. Ignoring
a law removes only that law from competition, not the whole group.

Semantics used (confirmed from vanilla examples):

- `unlocking_laws` = at least one of the listed laws
- `requires_law_or` = at least one of the listed laws
- `disallowing_laws` = none of the listed laws may be active
- `unlocking_technologies` = all listed technologies

This is deliberately stricter than the legal availability shown by the
politics panel. The panel can show a law with a Promulgar button while its
current checkpoint success chance is 0% (for example Supremacia Nacional in
the reported screenshot: 0% success, 52% debate and 47% delay). The advisor
uses the same engine value exposed by vanilla as
`enactment_chance_for_law(law_type:<law>)`, so it excludes only the impossible
case and does not invent a promise of success.

---

## 7. Scoring model

All values are generated in `common/script_values/sg_law_scores.txt`.

For each law:

- `sg_law_benefit_<law>`: `45 + sum(modifier contributions)` when the law has
  at least one positive measurable modifier; otherwise `30 + sum(...)`, clamped
  0–100. Contributions come from a hand-written rule table in
  `tools/build_law_data.py`. Pure interest-group power, voting-power and
  ideological `progressiveness` modifiers are deliberately ignored. A small
  situational adjustment is added only when the law's actual modifiers support
  that theme (bankruptcy risk, bureaucracy shortage, low literacy, low SoL, war,
  radicals). A law with no positive signal gets the neutral theme and no
  situational bonus.
- Tax laws are scored from the **average** of `tax_modifier_very_low`, `_low`,
  `_medium`, `_high` and `_very_high` per key, so brackets are not ignored.
- `sg_law_risk_<law>`: `5 + sum(risk contributions)`, clamped 0–60. Risk covers
  radicals, mortality, repression, discrimination, trade bans, migration bans,
  budget/bureaucracy cost, legitimacy loss, and similar real penalties. A small
  situational adjustment is added by risk theme; a law with no measurable risk
  uses the neutral risk theme. A powerful interest group that strongly
  disapproves adds 12 risk through `sg_law_powerful_opposition_<law>`, and the
  same flag drives the visible warning in the journal.
- `sg_law_politics_<law>`: iterates interest groups **in government**, adds
  `ig_clout * 60` for strongly approve, `* 30` for approve, subtracts the same
  for disapprove/strongly disapprove, then adds the ruler's
  `law_enactment_stance` (±8/±15). Clamped −50..50.
- `sg_law_merit_<law>`: `benefit + politics - risk * 0.5`, clamped −100..150.
  This is the country-fit measure used by the upgrade gate.
- `sg_law_score_<law>`: only if available:
  `merit + enactment_chance * 0.5`, clamped −100..200. `enactment_chance` is the
  current vanilla estimate expressed as 0–100; it penalizes difficult but
  possible laws without treating the estimate as a guarantee.
- `sg_law_current_merit_<group>` / `sg_law_upgrade_floor_<group>`: the active
  law's merit and that merit + 5, used to reject sidegrades.

The final top three is a global ranking of every law that passes the upgrade
gate. It does not reserve a slot per group, so the three rows can come from the
same group when those are genuinely the best alternatives. This is a
presentation/filtering rule; it does not change any generated score.

The final score is intentionally simple and explainable. The GUI shows the
three components separately so the player can see why a law is ranked.

---

## 8. GUI

`gui/journal_entry_widgets/sg_law_advisor.gui` is generated by
`tools/build_gui.py`. It is a 500-pixel vertical widget with:

- status bar: title, "advisor active", Disable button, refresh button
- last-refresh line showing the game month and year of the latest ranking
- explanatory header
- three recommendation rows, each with:
  - rank, law name, group and focus theme (hover = real effects + blocking requirements)
  - score, government support, benefit score, risk score
  - explicit score decomposition: benefit + government support - half of risk +
    half of estimated enactment chance
  - benefit sentence
  - risk sentence
  - one Enact and one Ignore button **per law**, visible only for the law the
    row currently displays
- explicit enactment-pause line shown while any law is being enacted, so the
  journal does not claim that the recommended laws are already in force when
  every availability trigger is temporarily false
- explicit empty state explaining that no available law can currently be
  recommended and pointing to requirements, active laws and ignored laws
- per-row warning when a powerful interest group strongly disapproves of the
  recommended law (+12 risk), using the same flag as the score
- footer: Clear ignored, Diagnostics, "recommendations only" note

Law names and tooltips are generated per stable numeric id. A row shows the
branch whose id matches `sg_top_N_id`; the branch uses localization keys such as
`sg_law_name_<sid>` and `sg_law_tip_<sid>`, whose text calls
`GetLawType('law_x')`. No law-type value is stored in a country variable.

Each recommendation is laid out as a vertical card with a separated header,
four fixed-width metric boxes, a bounded explanation panel and isolated action
buttons. The focus theme is rendered from the matching law branch, while the
benefit and risk sentences use that branch's law-specific localization keys.
This avoids a second dynamic selector and prevents long names, labels and
values from competing for the same horizontal line.
The visible decomposition is generated from the same stored component variables
used by the ranking formula; theme sentences are only summaries of measurable
modifier families, while the hover tooltip remains the authoritative source for
the game's exact effects and blocking requirements.

The widget wrappers do not set `autoresize`. In 1.15 that property is only
handled by textboxes; on a plain `widget` it produced 1,776 ignored-property
errors per load. `tools/validate.py` and the regression suite now reject it.
The diagnostic textbox visibility also uses a country-scope SGUI
(`sg_rank_diagnostic_visible_sgui`) because a direct
`MakeScope.HasVariable(...)` expression is not a valid data function and
aborted the GUI parse with a malformed-token error.

Law headers, action rows, explanation panels and ignored-law entries are plain
`widget` wrappers around a flowcontainer; removing the property changed no
layout because the engine already ignored it.

The status area also shows the latest ranking-cycle counters: laws checked,
available, ignored, no-real-gain, eligible and displayed. These counters are
reset at the start of every ranking pass and are removed when the advisor is
disabled, so a stale diagnostic cannot survive a deliberate disable.

During an enactment, every generated availability trigger is false because of
`NOT = { enacting_any_law = yes }`. The widget therefore shows a dedicated
pause line (`sg_enacting_visible_sgui`) and hides the generic empty state, so
an enactment in progress cannot be mistaken for "the recommended laws are
already in force".

---

## 9. What is done / what remains

Done in this phase:

- Added a dedicated journal state while a law is being enacted, replacing the
  misleading "already in force" empty message during that period.
- Fixed the never-selected legitimacy risk theme and added the visible
  powerful-opposition warning, backed by the same flag that adds the +12 risk.
- Shortened the header paragraph and moved the detailed scoring explanation to
  its tooltip.
- Replaced the one-per-group quota with a global top three and an upgrade gate:
  a law only appears when its merit beats the current law of its group by 5
  points, otherwise the journal shows the "already in force" empty state.
- Fixed the 1.15 `autoresize`-on-widget GUI errors reported by the live log.
  Added static validation and a regression test for the property.
- Fixed the GUI diagnostic visibility (`HasVariable` is not a data function) by
  using `sg_rank_diagnostic_visible_sgui`.
- Fixed three load-time script errors found in the live log: missing BOM in
  every script/localization file, `*_scope_interest_group` list names, the
  `radical_fraction` block-trigger syntax and the un-namespaced
  `LAW_MIN_SUCCESS_CHANCE` define.
- Verified a clean runtime load: the last startup produced zero errors from the
  mod, only nine benign "variable never set" warnings for legacy migration
  variables and the optional `sg_debug` switch.
- Parsed 148 laws across 26 groups from the real 1.15 install.
- Generated availability triggers, benefit/risk/politics/score values, ranking
  effect, enact/ignore effects, GUI and theme localization.
- Wrote the journal entry, lifecycle effects, scripted GUIs, decisions,
  additive on-actions and English/Portuguese UI localization.
- Addressed the Sourcery review: stable ids, schema migration, per-law button
  binding, rerank on failed enactment, modifier-based benefit/risk themes,
  neutral themes, all tax brackets, portable game discovery, launcher `.mod`
  file, lowercase localization keys, visible benefit score, and removal of the
  law-type variable path.
- Wrote this context file.

Still to do:

1. **Static validation.** Run `python3 tools/validate.py` after every generator
   run. It checks brace balance, law/technology references, scripted-name
   resolution, GUI SGUI references, localization keys, duplicate blocks,
   stable ids, the current-law merit gate and the rejected `autoresize`
   property. The standard-library regression suite is `python3 -m unittest
   discover -s tests -v`; it checks the 148-law inventory, stable ids, ranking
   sentinels, score/merit formula wiring, the upgrade gate, lifecycle cleanup,
   explanations and generated-file consistency.
2. **Runtime test.** Copy a save, back up `content_load.json`, install the mod,
   enable it, load the copy, open the journal, click Enact, ignore, refresh,
   disable and re-enable. Check `error.log` for script/GUI errors. The
   executable startup was verified under Wine (zero mod errors in the new
   `error*.log`), but this environment could not drive the graphical save/UI
   interaction. `-loadsave` was rejected for both the older test save and the
   current autosave ("Could not load save game"), so the ranking gate itself
   still needs one manual in-game confirmation.
3. **Fix runtime issues.** Most likely areas: the generated country-scope
   visibility SGUIs, the `law_stance`/`law_enactment_stance` values, or a vanilla
   trigger copied from `is_visible` that assumes a different scope.
4. **Git/PR.** Commit, push branch, reply to the Sourcery review, merge.

The reproducible manual checklist, including the exact existing test-save name
and log command, is in `docs/MANUAL_RUNTIME_TEST.md`. The current environment
can validate startup and logs under Wine but cannot provide reliable clicks in
the graphical save/UI flow, so interactive action results must be recorded by a
desktop-driven test session.

---

## 10. Fallbacks if a runtime feature fails

- **`GetLawType('law_x')` inside generated localization fails.** Fall back to
  per-law localization strings containing only static text, or store a law
  scope with `save_scope_as`/`value = PREV` and use the vanilla
  `Var('x').GetLaw.GetName` pattern. Do not return to storing a `law_type`
  token in a country variable.
- **Generated visibility SGUIs fail.** Check the country-scope equality in
  `sg_law_sguis.txt` and the matching generated SGUI name in the widget before
  changing the GUI expression strategy.
- **`law_enactment_stance` on ruler fails.** Remove the ruler block from
  `sg_law_politics_<law>`; interest-group stance alone is still valid.
- **`law_stance` in a script value fails.** Convert the politics value into a
  scripted effect that stores per-IG support in a variable, or use
  `any_scope_interest_group` conditions and weight only by count.
- **A copied `is_visible`/`can_enact` trigger errors.** Drop that block for the
  specific law and document the law as "availability not modelled"; never
  invent a replacement condition.
- **Storing law types in variables fails.** Not used anymore: the widget binds
  rows to stable numeric ids and resolves names through `GetLawType` inside
  localization. Do not reintroduce law-type variables.- **Comparing two script values in a trigger fails.** Replace the inline
  `sg_law_merit_<law> >= sg_law_upgrade_floor_<group>` gate with a precomputed
  boolean variable per law during the ranking pass, or store each group's
  current merit in a temporary `sg_group_*` variable before the law loop. Do not
  remove the gate and fill empty slots with sidegrades.

---

## 11. Compatibility rules

- Every scripted name starts with `sg_`.
- No vanilla file is overwritten.
- On-actions are extended with the additive `on_actions = { ... }` form.
- The mod only reads vanilla law data at build time; it does not patch it.
- The mod does not touch other automation mods' variables or decisions.
- Disabling removes all runtime state except the schema marker, so the mod can
  be removed from a save.
- Do not add a second journal entry per law category: one entry is deliberately
  used to avoid inactive-entry re-enable problems.
- `.metadata/metadata.json` is included so the game does not log a missing
  metadata file when loading a local installation.

---

## 12. Useful vanilla references

- `common/laws/*.txt` — law definitions, modifiers, requirements
- `common/law_groups/00_laws.txt` — group enable/change triggers
- `common/journal_entries/journal_entries.md` — JE schema
- `common/scripted_guis/scripted_guis.md` — scripted GUI schema
- `common/script_values/script_values.md` — script-value operations and lists
- `common/on_actions/_on_actions.md` — on-action list
- `gui/journal_entry.gui` — `custom_widget_container_3`
- `gui/politics_panel_change_law.gui` — real `GetEffectDesc` /
  `GetBlockingRequirements` usage
- `gui/shared/buttons.gui`, `gui/shared/defaults.gui` — button types
- `localization/english/modifiers_l_english.yml` — modifier display names
- Economy Advisor 1.15 reference mod:
  `/home/lincoln-ii/Downloads/3778129206_Economy_Advisor/3778129206 Economy Advisor/`
