#!/usr/bin/env python3
"""Generate the journal-entry widget.

The widget renders three ranked rows. Each row is bound to the stable numeric
law id stored in `sg_top_<slot>_id`; a generated per-law branch provides the
name, group and tooltip through localization keys that call GetLawType by key.
No law-type value is stored in a country variable.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "law_data.json"
OUT = ROOT / "gui" / "journal_entry_widgets" / "sg_law_advisor.gui"

BENEFIT_COUNT = 18  # 16 specific + neutral + generic positive
RISK_COUNT = 13  # 12 specific themes + neutral
FOCUS_COUNT = 6


def var(slot: int, field: str) -> str:
    return f"JournalEntry.GetCountry.MakeScope.Var('sg_top_{slot}_{field}')"


def law_visible(slot: int, law_id: str) -> str:
    return (
        f"[GetScriptedGui('sg_top_{slot}_law_{law_id}_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
    )


def law_header(slot: int, laws: list[dict]) -> str:
    branches = []
    for law in laws:
        sid = law["sid"]
        lid = law["id"]
        branches.append(
            f"""
				widget = {{
					visible = "{law_visible(slot, lid)}"
					autoresize = yes
					flowcontainer = {{
						direction = vertical
						spacing = 1
						ignoreinvisible = yes
						minimumsize = {{ 440 -1 }}
						maximumsize = {{ 440 42 }}

						textbox = {{
							autoresize = yes
							multiline = yes
							align = left|nobaseline
							using = fontsize_medium
							text = "sg_law_name_{sid}"
							tooltip = "sg_law_tip_{sid}"
							using = tooltip_se
						}}
						textbox = {{
							autoresize = yes
							multiline = yes
							align = left|nobaseline
							using = fontsize_medium
							default_format = "#weak"
							text = "sg_law_group_{sid}"
						}}
						textbox = {{
							autoresize = yes
							align = left|nobaseline
							using = fontsize_small
							default_format = "#weak"
							text = "sg_focus_{law['focus']}"
						}}
					}}
				}}"""
        )
    return "".join(branches)


def law_actions(slot: int, laws: list[dict]) -> str:
    """Generate one button pair per law, bound to that law's own SGUI.

    The pair is only visible while the row's stable id equals the law id, so the
    button the player clicks always belongs to the law the row displays.
    """
    branches = []
    for law in laws:
        lid = law["id"]
        branches.append(
            f"""
				widget = {{
					visible = "{law_visible(slot, lid)}"
					autoresize = yes
					flowcontainer = {{
						direction = horizontal
						spacing = 10
						ignoreinvisible = yes

						button = {{
							size = {{ 116 30 }}
							using = select_button_sound
							using = tooltip_se
							text = "sg_enact"
							tooltip = "sg_enact_tt"
							enabled = "[GetScriptedGui('sg_enact_law_{lid}_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
							onclick = "[GetScriptedGui('sg_enact_law_{lid}_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
						}}
						button = {{
							size = {{ 116 30 }}
							using = select_button_sound
							using = tooltip_se
							text = "sg_ignore"
							tooltip = "sg_ignore_tt"
							enabled = "[GetScriptedGui('sg_ignore_law_{lid}_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
							onclick = "[GetScriptedGui('sg_ignore_law_{lid}_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
						}}
					}}
				}}"""
        )
    return "".join(branches)


def row(slot: int, laws: list[dict]) -> str:
    visible = (
        f"[GetScriptedGui('sg_top_{slot}_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
    )
    return f"""
	# ---- recommendation {slot} -------------------------------------------------
	widget = {{
		visible = "{visible}"
		minimumsize = {{ 500 190 }}
		maximumsize = {{ 500 230 }}
		background = {{ using = dark_area }}

		flowcontainer = {{
			margin = {{ 10 8 }}
			direction = vertical
			spacing = 6
			ignoreinvisible = yes
			minimumsize = {{ 480 -1 }}
			maximumsize = {{ 480 -1 }}

			flowcontainer = {{
				direction = horizontal
				spacing = 8
				ignoreinvisible = yes

				textbox = {{
					size = {{ 28 28 }}
					align = left|nobaseline
					using = fontsize_medium
					default_format = "#high"
					raw_text = "{slot}."
				}}
{law_header(slot, laws)}
			}}

			flowcontainer = {{
				direction = horizontal
				spacing = 6
				ignoreinvisible = yes
{metric_box("sg_score_label", f"[{var(slot, 'score')}.GetValue|0", "#high")}
{metric_box("sg_support_label", f"[{var(slot, 'politics')}.GetValue|0", "#normal")}
{metric_box("sg_benefit_label", f"[{var(slot, 'benefit_score')}.GetValue|0", "#positive_value")}
{metric_box("sg_risk_label", f"[{var(slot, 'risk_score')}.GetValue|0", "#warning")}
			}}

			textbox = {{
				autoresize = yes
				multiline = yes
				align = left|nobaseline
				using = fontsize_small
				minimumsize = {{ 480 -1 }}
				maximumsize = {{ 480 -1 }}
				text = "sg_why_ranked_{slot}"
			}}
			flowcontainer = {{
				direction = vertical
				spacing = 2
				ignoreinvisible = yes
				minimumsize = {{ 480 36 }}
				maximumsize = {{ 480 56 }}
				background = {{ using = entry_bg_simple }}
{law_explanations(slot, laws)}
			}}
			flowcontainer = {{
				direction = horizontal
				spacing = 10
				parentanchor = hcenter
				ignoreinvisible = yes
{law_actions(slot, laws)}
			}}
		}}
	}}
"""


def metric_box(label: str, value: str, value_format: str) -> str:
    return f"""
				widget = {{
					size = {{ 115 34 }}
					background = {{ using = entry_bg_simple }}
					flowcontainer = {{
						direction = vertical
						spacing = 0
						margin = {{ 5 3 }}
						ignoreinvisible = yes
						textbox = {{
							autoresize = yes
							align = left|nobaseline
							using = fontsize_small
							default_format = "#weak"
							text = "{label}"
						}}
						textbox = {{
							autoresize = yes
							align = left|nobaseline
							using = fontsize_small
							default_format = "{value_format}"
							raw_text = "{value}]"
						}}
					}}
				}}"""


def law_explanations(slot: int, laws: list[dict]) -> str:
    branches = []
    for law in laws:
        lid = law["id"]
        branches.append(
            f"""
				widget = {{
					visible = "{law_visible(slot, lid)}"
					autoresize = yes
					flowcontainer = {{
						direction = vertical
						spacing = 1
						ignoreinvisible = yes
						textbox = {{
							autoresize = yes
							multiline = yes
							align = left|nobaseline
							using = fontsize_small
							minimumsize = {{ 480 -1 }}
							maximumsize = {{ 480 -1 }}
							text = "sg_law_benefit_{lid}"
						}}
						textbox = {{
							autoresize = yes
							multiline = yes
							align = left|nobaseline
							using = fontsize_small
							default_format = "#warning"
							minimumsize = {{ 480 -1 }}
							maximumsize = {{ 480 -1 }}
							text = "sg_law_risk_{lid}"
						}}
					}}
				}}"""
        )
    return "".join(branches)


def build() -> str:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    laws = data["laws"]
    rows = "".join(row(slot, laws) for slot in (1, 2, 3))
    empty_visible = (
        "[Not(GetScriptedGui('sg_top_1_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End))]"
    )
    # Or() only accepts 2 arguments, so nest: Or(Or(a, b), c)
    ignored_check = "GetScriptedGui('sg_ignored_{n}_visible_sgui').IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)"
    clear_visible = (
        f"[Or(Or({ignored_check.format(n=1)}, {ignored_check.format(n=2)}), "
        f"{ignored_check.format(n=3)})]"
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
				text = "sg_status_title"
			}}
			textbox = {{
				parentanchor = vcenter
				autoresize = yes
				align = left|nobaseline
				using = fontsize_medium
				default_format = "#positive_value"
				text = "sg_status_enabled"
			}}
		}}

		button = {{
			position = {{ -104 0 }}
			parentanchor = right|vcenter
			size = {{ 96 30 }}
			using = select_button_sound
			using = tooltip_se
			text = "sg_disable"
			tooltip = "sg_disable_tt"
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
			tooltip = "sg_refresh_tt"
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
		text = "sg_last_refresh"
	}}

	textbox = {{
		visible = "[JournalEntry.GetCountry.MakeScope.HasVariable('sg_last_rank_evaluated')]"
		autoresize = yes
		multiline = yes
		align = left|nobaseline
		using = fontsize_small
		default_format = "#weak"
		minimumsize = {{ 500 -1 }}
		maximumsize = {{ 500 -1 }}
		text = "sg_rank_diagnostic"
	}}

	textbox = {{
		autoresize = yes
		multiline = yes
		align = left|nobaseline
		using = fontsize_small
		default_format = "#weak"
		minimumsize = {{ 500 -1 }}
		maximumsize = {{ 500 -1 }}
		text = "sg_header"
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
		text = "sg_empty"
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
			text = "sg_clear_ignored"
			tooltip = "sg_clear_ignored_tt"
			onclick = "[GetScriptedGui('sg_clear_ignored_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
		button = {{
			size = {{ 150 28 }}
			using = select_button_sound
			using = tooltip_se
			text = "sg_diagnostics"
			tooltip = "sg_diagnostics_tt"
			onclick = "[GetScriptedGui('sg_diagnostics_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
		}}
		textbox = {{
			autoresize = yes
			align = left|nobaseline
			using = fontsize_small
			default_format = "#weak"
			text = "sg_footer_note"
		}}
	}}
}}
"""


def main() -> int:
    if not DATA.is_file():
        raise SystemExit(
            f"Missing {DATA}. Run tools/build_law_data.py before tools/build_gui.py."
        )
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(build(), encoding="utf-8")
    print(f"Wrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
