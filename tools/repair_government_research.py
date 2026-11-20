"""Repair the installed contextual research advisor without regenerating other modules."""
import argparse
import json
import re
import shutil
import zlib
from pathlib import Path

try:
    from .research_script_parser import parse
except ImportError:
    from research_script_parser import parse


def technologies(game):
    result = {}
    for path in sorted((game / 'common/technology/technologies').glob('*.txt')):
        for entry in parse(path.read_text(encoding='utf-8-sig')):
            if not isinstance(entry.value, list):
                continue
            fields = {field.key: field.value for field in entry.value}
            if fields.get('can_research') == 'no':
                continue
            result[entry.key] = {
                'category': fields.get('category'),
                'era': int(str(fields.get('era', 'era_1')).split('_')[-1]),
                'requirements': [e.key for e in fields.get('unlocking_technologies', [])],
            }
    return result


def repair(source, game, output):
    shutil.copytree(source, output)
    rank_path = output / 'common/scripted_effects/sg_research_rank.txt'
    rank = rank_path.read_text(encoding='utf-8-sig')
    if 'sg_research_general_fallback' in rank:
        raise ValueError('Research repair is already installed.')
    rank = rank.replace('\t\tremove_variable = sg_research_candidate_id',
                        '\t\tif = { limit = { var:sg_research_1_id = 0 } sg_research_general_fallback = yes }\n\t\tremove_variable = sg_research_candidate_id', 1)
    effects = ['sg_research_general_fallback = {']
    availability = []
    guis = []
    widgets = []
    locales = {'braz_por': [], 'english': []}
    ids = set(int(v) for v in re.findall(r'sg_research_candidate_id value = (\d+)', rank))
    for tech, data in technologies(game).items():
        identity = zlib.crc32(('general:' + tech).encode()) & 0x7fffffff
        if identity in ids or identity == 0:
            raise ValueError('Technology ID collision.')
        ids.add(identity)
        trigger = f'sg_research_general_available_{tech}'
        availability.append(f'''{trigger} = {{
 NOT = {{ has_technology_researched = {tech} }}
 NOT = {{ is_researching_technology = {tech} }}
''' + '\n'.join(f' has_technology_researched = {req}' for req in data['requirements']) + '\n}')
        score = 100 - data['era'] * 10 + {'production': 3, 'society': 2, 'military': 1}.get(data['category'], 0)
        effects.append(f''' if = {{ limit = {{ {trigger} = yes }}
  set_variable = {{ name = sg_research_candidate_id value = {identity} }}
  set_variable = {{ name = sg_research_candidate_score value = {score} }}
  sg_research_insert = yes
 }}''')
        for slot in (1, 2, 3):
            key = f'sg_research_general_{slot}_{tech}'
            guis.append(f'''{key}_sgui = {{
 scope = country
 is_shown = {{ has_variable = sg_research_{slot}_id var:sg_research_{slot}_id = {identity} {trigger} = yes }}
}}''')
            widgets.append(f'''textbox = {{
 visible = "[GetScriptedGui('{key}_sgui').IsShown(GuiScope.SetRoot(JournalEntry.GetCountry.MakeScope).End)]"
 autoresize = yes multiline = yes align = left|nobaseline using = fontsize_small
 minimumsize = {{ 484 -1 }} maximumsize = {{ 484 -1 }}
 text = "{key}"
}}''')
            title = f"[GetTechnology('{tech}').GetNameNoFormatting]"
            category = {'production': ('Produção', 'Production'), 'society': ('Sociedade', 'Society'),
                        'military': ('Militar', 'Military')}.get(data['category'], ('Tecnologia', 'Technology'))
            locales['braz_por'].append(f' {key}:0 "Prioridade {slot} · {title}\\nSugestão geral para continuar avançando. Pré-requisitos pesquisados. Tecnologias de eras anteriores têm preferência.\\nAbra Tecnologia → {category[0]} e confira os efeitos antes de iniciar."')
            locales['english'].append(f' {key}:0 "Priority {slot} · {title}\\nGeneral suggestion to keep progressing. Prerequisites researched. Earlier eras have priority.\\nOpen Technology → {category[1]} and review effects before starting."')
    effects.append('}')
    rank_path.write_text(rank + '\n' + '\n'.join(effects), encoding='utf-8-sig')
    paths = {
        'common/scripted_triggers/sg_research_general.txt': '\n'.join(availability),
        'common/scripted_guis/sg_research_general.txt': '\n'.join(guis),
    }
    for language, lines in locales.items():
        paths[f'localization/{language}/sg_research_general_l_{language}.yml'] = f'l_{language}:\n' + '\n'.join(lines)
    for path, text in paths.items():
        (output / path).write_text(text + '\n', encoding='utf-8-sig')
    gui_path = output / 'gui/journal_entry_widgets/sg_law_advisor.gui'
    gui = gui_path.read_text(encoding='utf-8-sig')
    needle = 'text = "sg_research_empty"\n\t\t}'
    if gui.count(needle) != 1:
        raise ValueError('Unexpected research widget.')
    gui_path.write_text(gui.replace(needle, needle + '\n' + '\n'.join(widgets)), encoding='utf-8-sig')
    path = output / 'common/on_actions/sg_research_on_actions.txt'
    text = path.read_text(encoding='utf-8-sig')
    text += '\non_monthly_pulse_country = { on_actions = { sg_research_update } }\n'
    path.write_text(text, encoding='utf-8-sig')
    metadata_path = output / '.metadata/metadata.json'
    metadata = json.loads(metadata_path.read_text(encoding='utf-8-sig'))
    metadata['version'] = '1.0.2'
    metadata_path.write_text(json.dumps(metadata, indent=2) + '\n')
    descriptor = output / 'descriptor.mod'
    descriptor.write_text(re.sub(r'(?m)^version="[^"]+"', 'version="1.0.2"',
                                descriptor.read_text()), encoding='utf-8')
    return len(availability)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--game', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(repair(args.source, args.game, args.output))
