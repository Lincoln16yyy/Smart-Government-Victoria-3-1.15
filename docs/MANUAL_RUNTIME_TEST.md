# Manual runtime test — Smart Government Advisor

This procedure uses a copy of the Haiti save and must not be run on the only
copy of a campaign.

## Preparation

1. Close Victoria 3.
2. Back up the active load order before changing it:

   ```bash
   USER_DIR="$HOME/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3"
   BACKUP="$USER_DIR/content_load.json.sg-backup"
   test ! -e "$BACKUP" || {
     echo "Backup already exists; restore or rename it before continuing." >&2
     exit 1
   }
   cp -- "$USER_DIR/content_load.json" "$BACKUP"
   ```

3. Install the current working tree:

   ```bash
   python3 tools/install_mod.py --user-dir "$USER_DIR" --force
   ```

4. Enable **Smart Government Advisor** in the launcher. Do not remove or
   reorder the other enabled mods.
5. Load this separate save:

   `save games/haiti_1836_06_30_SG_TEST.v3`

## Action checklist

Use the journal entry **Smart Government**. Record the visible recommendation
names and the last-refresh month/year before each action.

| Action | Expected result |
| --- | --- |
| Enable, if the entry is not already present | The enable decision creates the journal entry, populates up to three rows, and sets a refresh date. |
| Refresh | The rows and refresh date are recalculated immediately; no law starts by itself. |
| Ranking status line | The widget reports the checked, available, eligible, ignored and shown counts for the latest cycle; the checked count should match the generated law count for this game data. |
| Hover a law name | The tooltip shows the game's current effects and blocking requirements for that law. |
| Ignore one recommendation | That law disappears after reranking and is not immediately recommended again. |
| Ignore up to three recommendations | Each ignored law stays out of the list. If a fourth is ignored, the newest ignored law in slot 3 is replaced. |
| Clear ignored | Previously ignored laws become eligible again after reranking. |
| Enact one recommendation | The normal law enactment process opens/starts for the selected law; the law is not approved instantly. |
| While a law is being enacted | Enact buttons are disabled, while Refresh, Ignore, Clear ignored and Disable remain usable where applicable. |
| Disable from the journal | The entry disappears/inactivates, runtime and ranking-diagnostic variables are removed, and any enactment already in progress is untouched. |
| Re-enable with the decision | A fresh entry and fresh ranking are created. The advisor does not silently re-enable before this step. |
| Advance one month | The monthly pulse updates the recommendations and refresh date without creating a duplicate journal entry. |

After each click, wait for the journal widget to redraw before judging the row
or button state. Save the test copy after a meaningful checkpoint if the game
session must be resumed.

## Cleanup

After closing Victoria 3 and finishing the log checks, restore the original
load order so later campaigns are unaffected:

```bash
cp -- "$BACKUP" "$USER_DIR/content_load.json"
rm -- "$BACKUP"
```

If the test is interrupted, run the cleanup commands before launching another
campaign. The mod folder itself may remain installed; only the load order is
restored.

## Log checks

Inspect the game logs after closing the test session:

```bash
LOG_DIR="$HOME/.config/hydralauncher/wine-prefixes/529340/drive_c/users/steamuser/Documents/Paradox Interactive/Victoria 3/logs"
grep -nEi 'sg_|Smart Government|sg_law_advisor|FetchData|script error|unknown scripted' \
  "$LOG_DIR/error.log" "$LOG_DIR/game.log"
```

Expected: no advisor-specific parse, localization, scripted-GUI or
`FetchData` errors. Warnings from unrelated enabled mods should be recorded
separately rather than attributed to this mod.

## Current environment limitation

The repository environment can start the Victoria 3 executable under Wine and
inspect its logs, but it does not provide reliable graphical control for
loading this save and clicking the journal controls. Therefore the checklist
above is prepared for a human or desktop-driven session; startup/log
validation alone does not count as verification of the interactive actions.
