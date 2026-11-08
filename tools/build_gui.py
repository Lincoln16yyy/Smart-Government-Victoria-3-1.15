#!/usr/bin/env python3
"""Generate the journal-entry widget.

The only generated part is the nested SelectLocalization expression that turns
a numeric theme code stored in a country variable into a localized sentence.
Keeping that expression generated avoids hand-editing a very long line.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "gui" / "journal_entry_widgets" / "sg_law_advisor.gui"

BENEFIT_COUNT = 16
RISK_COUNT = 12
FOCUS_COUNT = 6


def selector(variable: str, prefix: str, count: int) -> str:
    expr = f"'{prefix}_{count}'"
    for i in range(count - 1, 0, -1):
        expr = (
            f"SelectLocalization(LessThan_int32("
            f"JournalEntry.GetCountry.MakeScope.Var('{variable}').GetValue, "
            f"'(int32){i + 1}'), '{prefix}_{i}', {expr})"
        )
    return f"[{expr}]"


def var(slot: int, field: str) -> str:
    return f"JournalEntry.GetCountry.MakeScope.Var('sg_top_{slot}_{field}')"


def law(slot: int) -> str:
    return f"{var(slot, 'law')}.GetLawType"


def row(slot: int) -> str:
    benefit = selector(f"sg_top_{slot}_benefit", "sg_benefit", BENEFIT_COUNT)
    risk = selector(f"sg_top_{slot}_risk", "sg_risk", RISK_COUNT)
    focus = selector(f"sg_top_{slot}_focus", "sg_focus", FOCUS_COUNT)
    visible = (
        f"[GetScriptedGui('sg_top_{slot}_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
    )
    effect_tip = f"[{law(slot)}.GetEffectDesc(GetPlayer.Self)]"
    block_tip = f"[{law(slot)}.GetBlockingRequirements(GetPlayer.Self)]"
    return f"""
	# ---- recommendation {slot} -------------------------------------------------
	widget = {{
		visible = "{visible}"
		minimumsize = {{ 500 -1 }}
		maximumsize = {{ 500 -1 }}
		background = {{ using = dark_area }}

		flowcontainer = {{
			position = {{ 10 7 }}
			direction = vertical
			spacing = 2
			ignoreinvisible = yes
			minimumsize = {{ 480 -1 }}
			maximumsize = {{ 480 -1 }}

			flowcontainer = {{
				direction = horizontal
				spacing = 6
				ignoreinvisible = yes

				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_medium
					default_format = "#high"
					raw_text = "{slot}."
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_medium
					text = "[{law(slot)}.GetName]"
					tooltip = "{effect_tip}"
					using = tooltip_se
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_medium
					default_format = "#weak"
					text = "[{law(slot)}.GetGroup.GetName]"
				}}
			}}

			flowcontainer = {{
				direction = horizontal
				spacing = 10
				ignoreinvisible = yes

				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					default_format = "#weak"
					text = "{focus}"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					text = "SG_SCORE_LABEL"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					default_format = "#high"
					raw_text = "[{var(slot, 'score')}.GetValue|0]"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					text = "SG_SUPPORT_LABEL"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					raw_text = "[{var(slot, 'politics')}.GetValue|0]"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					text = "SG_RISK_LABEL"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					raw_text = "[{var(slot, 'risk_score')}.GetValue|0]"
				}}
			}}

			textbox = {{
				autoresize = yes
				multiline = yes
				align = left|nobaseline
				using = fontsize_small
				minimumsize = {{ 480 -1 }}
				maximumsize = {{ 480 -1 }}
				text = "{benefit}"
			}}
			textbox = {{
				autoresize = yes
				multiline = yes
				align = left|nobaseline
				using = fontsize_small
				default_format = "#warning"
				minimumsize = {{ 480 -1 }}
				maximumsize = {{ 480 -1 }}
				text = "{risk}"
			}}
			flowcontainer = {{
				direction = horizontal
				spacing = 8
				ignoreinvisible = yes

				button = {{
					size = {{ 100 28 }}
					using = select_button_sound
					using = tooltip_se
					text = "SG_ENACT"
					tooltip = "SG_ENACT_TT"
					enabled = "[GetScriptedGui('sg_enact_{slot}_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
					onclick = "[GetScriptedGui('sg_enact_{slot}_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
				}}
				button = {{
					size = {{ 100 28 }}
					using = select_button_sound
					using = tooltip_se
					text = "SG_IGNORE"
					tooltip = "SG_IGNORE_TT"
					enabled = "[GetScriptedGui('sg_ignore_{slot}_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
					onclick = "[GetScriptedGui('sg_ignore_{slot}_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
				}}
				textbox = {{
					visible = "[Not(StringIsEmpty({block_tip}))]"
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					default_format = "#warning"
					text = "SG_REQUIREMENTS_HINT"
					tooltip = "{block_tip}"
					using = tooltip_se
				}}
				textbox = {{
					visible = "[Not(StringIsEmpty({effect_tip}))]"
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					default_format = "#weak"
					text = "SG_EFFECTS_HINT"
					tooltip = "{effect_tip}"
					using = tooltip_se
				}}
			}}
		}}
	}}
"""


def build() -> str:
    rows = "".join(row(slot) for slot in (1, 2, 3))
    empty_visible = (
        "[Not(GetScriptedGui('sg_top_1_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End))]"
    )
    clear_visible = (
        "[Or(GetScriptedGui('sg_ignored_1_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End), "
        "GetScriptedGui('sg_ignored_2_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End), "
        "GetScriptedGui('sg_ignored_3_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End))]"
    )
    return f"""# Smart Government Advisor journal widget.
# Generated by tools/build_gui.py - edit the generator, not this file.

flowcontainer = {{
	name = "sg_law_advisor_widget"
	minimumsize = {{ 500 -1 }}
	maximumsize = {{ 500 -1 }}
	direction = vertical
	spacing = 4
	ignoreinvisible = yes

	# ---- status ---------------------------------------------------------------
	widget = {{
		size = {{ 500 42 }}
		background = {{ using = dark_area }}

		flowcontainer = {{
			position = {{ 8 0 }}
			parentanchor = vcenter
			direction = horizontal
			spacing = 6
			ignoreinvisible = yes

			icon = {{
				parentanchor = vcenter
				size = {{ 30 30 }}
				texture = "gfx/interface/icons/law_icons/autocracy.dds"
			}}
			textbox = {{
				parentanchor = vcenter
				autoresize = yes
				align = left|nobaseline
				using = fontsize_medium
				text = "SG_STATUS_TITLE"
			}}
			textbox = {{
				parentanchor = vcenter
				autoresize = yes
				align = left|nobaseline
				using = fontsize_medium
				default_format = "#P"
				text = "SG_STATUS_ENABLED"
			}}
		}}

		button = {{
			position = {{ -104 0 }}
			parentanchor = right|vcenter
			size = {{ 96 30 }}
			using = select_button_sound
			using = tooltip_se
			text = "SG_DISABLE"
			tooltip = "SG_DISABLE_TT"
			enabled = "[GetScriptedGui('sg_disable_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
			onclick = "[GetScriptedGui('sg_disable_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
		button_icon_round_action = {{
			position = {{ -6 0 }}
			parentanchor = right|vcenter
			size = {{ 32 32 }}
			blockoverride "icon" {{
				texture = "gfx/interface/buttons/button_icons/reset.dds"
			}}
			using = select_button_sound
			using = tooltip_se
			tooltip = "SG_REFRESH_TT"
			enabled = "[GetScriptedGui('sg_refresh_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
			onclick = "[GetScriptedGui('sg_refresh_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
	}}

	textbox = {{
		autoresize = yes
		multiline = yes
		align = left|nobaseline
		using = fontsize_small
		default_format = "#weak"
		minimumsize = {{ 500 -1 }}
		maximumsize = {{ 500 -1 }}
		text = "SG_HEADER"
	}}

{rows}
	# ---- empty state ----------------------------------------------------------
	textbox = {{
		visible = "{empty_visible}"
		autoresize = yes
		multiline = yes
		align = left|nobaseline
		using = fontsize_medium
		default_format = "#weak"
		minimumsize = {{ 500 -1 }}
		maximumsize = {{ 500 -1 }}
		text = "SG_EMPTY"
	}}

	# ---- footer ---------------------------------------------------------------
	flowcontainer = {{
		direction = horizontal
		spacing = 8
		ignoreinvisible = yes

		button = {{
			visible = "{clear_visible}"
			size = {{ 150 28 }}
			using = select_button_sound
			using = tooltip_se
			text = "SG_CLEAR_IGNORED"
			tooltip = "SG_CLEAR_IGNORED_TT"
			onclick = "[GetScriptedGui('sg_clear_ignored_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
		button = {{
			size = {{ 150 28 }}
			using = select_button_sound
			using = tooltip_se
			text = "SG_DIAGNOSTICS"
			tooltip = "SG_DIAGNOSTICS_TT"
			onclick = "[GetScriptedGui('sg_diagnostics_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
		textbox = {{
			autoresize = yes
			align = left|nobaseline
			using = fontsize_small
			default_format = "#weak"
			text = "SG_FOOTER_NOTE"
		}}
	}}
}}
"""


def main() -> int:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
