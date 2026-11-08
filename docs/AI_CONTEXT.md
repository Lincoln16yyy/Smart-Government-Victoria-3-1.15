# Smart Government Advisor — AI context file

This file is the hand-off document for another AI or developer picking up this
repository. It records the design, the exact game/save paths on the original
machine, what is generated, what is hand-written, what has been verified, and
what still needs a runtime test.

Last updated: 2026-11-07 (phase 4: Sourcery review fixes; schema 2).

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
2. **Journal entry.** `sg_ensure_journal_entry` adds
   `je_sg_law_advisor` if neither the active nor the inactive entry exists.
3. **Evaluation.** `sg_rank_laws` first calls `sg_migrate_schema` (schema 1
   positional state is discarded), sets every top slot to `-1000`, then iterates
   all 148 laws. For each law it checks `sg_law_available_<law>` and the ignored
   list, compares `sg_law_score_<law>` against the current top three and stores
   the **stable numeric law id**, score, benefit theme, risk theme, focus theme,
   benefit score, risk score and political score.
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

Other variables:

- `sg_enabled` — advisor is on
- `sg_schema_version` — schema marker (2; never removed on disable)
- `sg_ignored_1..3` — stable numeric law ids
- `sg_ignored_selected` — short-lived helper for the ignore effect
- `sg_debug` — optional; enables lifecycle `debug_log` messages

---

## 6. Availability model

For every law, `tools/build_law_data.py` writes
`sg_law_available_<law_id>`. It contains:

- `NOT = { has_law_or_variant = law_type:<law> }` (do not recommend current law)
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

Semantics used (confirmed from vanilla examples):

- `unlocking_laws` = at least one of the listed laws
- `requires_law_or` = at least one of the listed laws
- `disallowing_laws` = none of the listed laws may be active
- `unlocking_technologies` = all listed technologies

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
  budget/bureaucracy cost, and similar real penalties. A small situational
  adjustment is added by risk theme; a law with no measurable risk uses the
  neutral risk theme.
- `sg_law_politics_<law>`: iterates interest groups **in government**, adds
  `ig_clout * 60` for strongly approve, `* 30` for approve, subtracts the same
  for disapprove/strongly disapprove, then adds the ruler's
  `law_enactment_stance` (±8/±15). Clamped −50..50.
- `sg_law_score_<law>`: only if available:
  `benefit + politics - risk * 0.5`, clamped −100..200.

The final score is intentionally simple and explainable. The GUI shows the
three components separately so the player can see why a law is ranked.

---

## 8. GUI

`gui/journal_entry_widgets/sg_law_advisor.gui` is generated by
`tools/build_gui.py`. It is a 500-pixel vertical widget with:

- status bar: title, "advisor active", Disable button, refresh button
- explanatory header
- three recommendation rows, each with:
  - rank, law name and group (hover = real effects + blocking requirements)
  - focus theme, score, government support, benefit score, risk score
  - benefit sentence
  - risk sentence
  - one Enact and one Ignore button **per law**, visible only for the law the
    row currently displays
- empty state
- footer: Clear ignored, Diagnostics, "recommendations only" note

Law names and tooltips are generated per stable numeric id. A row shows the
branch whose id matches `sg_top_N_id`; the branch uses localization keys such as
`sg_law_name_<sid>` and `sg_law_tip_<sid>`, whose text calls
`GetLawType('law_x')`. No law-type value is stored in a country variable.

Theme sentences are selected from numeric variables with nested
`SelectLocalization(LessThan_int32(...), ...)`. Index 0 is a neutral fallback
for the short moment before a row variable is written. The per-law localization
keys `sg_law_benefit_<law>` and `sg_law_risk_<law>` still exist for modders.

---

## 9. What is done / what remains

Done in this phase:

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
   resolution, GUI SGUI references, localization keys, duplicate blocks and
   stable ids.
2. **Runtime test.** Copy a save, back up `content_load.json`, install the mod,
   enable it, load the copy, open the journal, click Enact, ignore, refresh,
   disable and re-enable. Check `error.log` for script/GUI errors.
3. **Fix runtime issues.** Most likely areas: the
   `GreaterThan_int32`/`LessThan_int32` id branches, the
   `law_stance`/`law_enactment_stance` values, or a vanilla trigger copied from
   `is_visible` that assumes a different scope.
4. **Git/PR.** Commit, push branch, reply to the Sourcery review, merge.

---

## 10. Fallbacks if a runtime feature fails

- **`GetLawType('law_x')` inside generated localization fails.** Fall back to
  per-law localization strings containing only static text, or store a law
  scope with `save_scope_as`/`value = PREV` and use the vanilla
  `Var('x').GetLaw.GetName` pattern. Do not return to storing a `law_type`
  token in a country variable.
- **`GreaterThan_int32`/`LessThan_int32` id branches fail.** Replace the exact
  id check with one `<` chain generated by `build_gui.py`, or use
  `SelectLocalization` to choose a per-law localization key.
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
  localization. Do not reintroduce law-type variables.

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
