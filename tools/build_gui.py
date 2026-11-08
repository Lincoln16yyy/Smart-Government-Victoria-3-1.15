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


def exact_id(slot: int, sid: int) -> str:
    """Return a GUI boolean expression that is true for exactly one id."""
    value = f"{var(slot, 'id')}.GetValue"
    return (
        f"And(GreaterThan_int32({value}, '(int32){sid - 1}'), "
        f"LessThan_int32({value}, '(int32){sid + 1}'))"
    )


def law_header(slot: int, laws: list[dict]) -> str:
    branches = []
    for law in laws:
        sid = law["sid"]
        branches.append(
            f"""
				widget = {{
					visible = "[{exact_id(slot, sid)}]"
					autoresize = yes
					flowcontainer = {{
						direction = horizontal
						spacing = 6
						ignoreinvisible = yes

						textbox = {{
							autoresize = yes
							align = left|nobaseline
							using = fontsize_medium
							text = "sg_law_name_{sid}"
							tooltip = "sg_law_tip_{sid}"
							using = tooltip_se
						}}
						textbox = {{
							autoresize = yes
							align = left|nobaseline
							using = fontsize_medium
							default_format = "#weak"
							text = "sg_law_group_{sid}"
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
        sid = law["sid"]
        branches.append(
            f"""
				widget = {{
					visible = "[{exact_id(slot, sid)}]"
					autoresize = yes
					flowcontainer = {{
						direction = horizontal
						spacing = 8
						ignoreinvisible = yes

						button = {{
							size = {{ 100 28 }}
							using = select_button_sound
							using = tooltip_se
							text = "sg_enact"
							tooltip = "sg_enact_tt"
							enabled = "[GetScriptedGui('sg_enact_law_{lid}_sgui').IsValid(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
							onclick = "[GetScriptedGui('sg_enact_law_{lid}_sgui').Execute(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
						}}
						button = {{
							size = {{ 100 28 }}
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
    benefit = selector(f"sg_top_{slot}_benefit", "sg_benefit", BENEFIT_COUNT)
    risk = selector(f"sg_top_{slot}_risk", "sg_risk", RISK_COUNT)
    focus = selector(f"sg_top_{slot}_focus", "sg_focus", FOCUS_COUNT)
    visible = (
        f"[GetScriptedGui('sg_top_{slot}_visible_sgui')"
        ".IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
    )
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
{law_header(slot, laws)}
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
					text = "sg_score_label"
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
					text = "sg_support_label"
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
					text = "sg_benefit_label"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					raw_text = "[{var(slot, 'benefit_score')}.GetValue|0]"
				}}
				textbox = {{
					autoresize = yes
					align = left|nobaseline
					using = fontsize_small
					text = "sg_risk_label"
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
{law_actions(slot, laws)}
			}}
		}}
	}}
"""


def build() -> str:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    laws = data["laws"]
    rows = "".join(row(slot, laws) for slot in (1, 2, 3))
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
				text = "sg_status_title"
			}}
			textbox = {{
				parentanchor = vcenter
				autoresize = yes
				align = left|nobaseline
				using = fontsize_medium
				default_format = "#P"
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
