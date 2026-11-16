"""Gera uma edição do Smart Government Advisor para Better Politics."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from tools.pdx_parse import TOKEN_RE, strip_comments

NAME = 'Smart Government Advisor - Better Politics'
RUNTIME = ('common', 'gui', 'localization')
BPM_ID = '2932134122'
HEADER = re.compile(r'(?:(INJECT|REPLACE):)?((?:law|lawgroup)_\w+)')
LIST_FIELDS = {'unlocking_technologies', 'unlocking_laws', 'requires_law_or', 'disallowing_laws'}
TRIGGER_FIELDS = {'can_enact', 'is_visible', 'enable', 'change_allowed_trigger'}


def fields(script):
    """Retém operadores, aspas e escopos do script usado pelo gerador."""
    tokens = TOKEN_RE.findall(strip_comments(script))
    i = 0
    while i < len(tokens):
        key = tokens[i]
        if i + 1 == len(tokens) or tokens[i + 1] not in {'=', '<', '>', '>=', '<=', '!=', '?='}:
            yield key, '', ''
            i += 1
            continue
        op = tokens[i + 1]
        start = i + 2
        i = start + 1
        if tokens[start] == '{':
            depth = 1
            while depth:
                depth += (tokens[i] == '{') - (tokens[i] == '}')
                i += 1
        yield key, op, ' '.join(tokens[start:i])


def inject(previous, addition):
    """Consolida campos repetidos que o leitor do Advisor acessa uma vez."""
    merged = {key: (op, value) for key, op, value in fields(previous)}
    for key, op, value in fields(addition):
        if key in merged and (key in LIST_FIELDS | TRIGGER_FIELDS
                              or key in {'modifier', 'institution_modifier'}
                              or key.startswith('tax_modifier_')):
            old = merged[key][1]
            if key in LIST_FIELDS | TRIGGER_FIELDS:
                value = f'{{ {old[1:-1]} {value[1:-1]} }}'
            else:
                modifiers = {k: (o, v) for k, o, v in fields(old[1:-1])}
                modifiers.update({k: (o, v) for k, o, v in fields(value[1:-1])})
                value = '{ ' + ' '.join(f'{k} {o} {v}' for k, (o, v) in modifiers.items()) + ' }'
        merged[key] = op, value
    return '\n'.join(f'{key} {op} {value}' for key, (op, value) in merged.items())


def make_database(game, bpm, destination):
    for category in ('laws', 'law_groups', 'technology', 'static_modifiers'):
        folder = Path('common') / category
        output = destination / folder
        output.mkdir(parents=True)
        if category in {'technology', 'static_modifiers'}:
            for root in (game, bpm):
                for path in sorted((root / folder).rglob('*.txt')):
                    target = output / path.relative_to(root / folder)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(path, target)
            continue
        sources = {path.name: path for root in (game, bpm) for path in (root / folder).glob('*.txt')}
        database = {}
        for path in sorted(sources.values(), key=lambda path: path.name):
            script = path.read_text(encoding='utf-8-sig')
            for key, op, value in fields(script):
                match = HEADER.fullmatch(key)
                if not match or op != '=' or not value.startswith('{'):
                    continue
                mode, name = match.groups()
                body = value[1:-1]
                database[name] = inject(database[name], body) if mode == 'INJECT' else body
        (output / 'sg_bpm_inputs.txt').write_text(
            '\n'.join(f'{key} = {{\n{body}\n}}' for key, body in database.items()), encoding='utf-8-sig')


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError(f'Unexpected Smart Government generator near {old!r}.')
    return text.replace(old, new, 1)


def guard_ranking(text):
    for slot in (1, 2, 3):
        text = replace_once(text, f' > var:sg_top_{slot}_score ', f' > sg_cwe_top_{slot}_score_or_empty ')
        needle = f'limit = {{ var:sg_top_{slot}_id > 0 }}'
        text = replace_once(text, needle,
                            f'limit = {{ has_variable = sg_top_{slot}_id var:sg_top_{slot}_id > 0 }}')
    for slot in (1, 2):
        old = f'has_variable = sg_top_{slot}_id }} sg_copy_top_{slot}_to_{slot + 1}'
        new = (f'has_variable = sg_top_{slot}_id var:sg_top_{slot}_id > 0 '
               f'has_variable = sg_top_{slot}_score }} sg_copy_top_{slot}_to_{slot + 1}')
        if text.count(old) != slot:
            raise ValueError(f'Unexpected Smart Government shift logic for slot {slot}.')
        text = text.replace(old, new)
    return text


def score_fallbacks():
    return '\n'.join(f'''sg_cwe_top_{slot}_score_or_empty = {{
 value = 0
 if = {{ limit = {{ has_variable = sg_top_{slot}_score }} add = var:sg_top_{slot}_score }}
 if = {{ limit = {{ NOT = {{ has_variable = sg_top_{slot}_score }} }} subtract = 1000 }}
}}
''' for slot in (1, 2, 3))


def adapt_generator(path):
    text = path.read_text(encoding='utf-8-sig')
    # The engine's start chance remains mandatory. Repeatables are BPM actions.
    needle = '        lines.append("\\tNOT = { enacting_any_law = yes }")'
    text = replace_once(text, needle, needle + '''
        if law["group"].startswith(("lawgroup_repeatable_", "lawgroup_box_of_")):
            out += [lines[0], "\\talways = no", "}", ""]
            continue''')
    start = text.index('        out.append(f"sg_law_politics_{lid} = {{")')
    end = text.index('        out.append(f"sg_law_enactment_chance_{lid}', start)
    text = text[:start] + '''        group = law["group"]
        out.append(f"sg_bpm_stance_{lid} = {{")
        out.append("\\tvalue = 0")
        for stance, steps in (("strongly_approve", 2), ("approve", 1),
                              ("disapprove", -1), ("strongly_disapprove", -2)):
            out.append(f"\\tif = {{ limit = {{ law_stance = {{ law = law_type:{lid} value = {stance} }} }} add = {steps} }}")
        out.append("}")
        out.append(f"sg_law_politics_{lid} = {{")
        out.append("\\tvalue = 0")
        out.append("\\tevery_interest_group = {")
        out.append("\\t\\tlimit = { bpm_ig_is_marginal = no }")
        out.append(f"\\t\\tadd = {{ value = sg_bpm_stance_{lid} subtract = sg_bpm_current_stance_{group} multiply = ig_clout }}")
        out.append("\\t}")
        out.append("\\tmultiply = 25")
        out.append("}")
        out.append("")
''' + text[end:]
    needle = '    for group in sorted(by_group):'
    text = replace_once(text, needle, needle + '''
        out.append(f"sg_bpm_current_stance_{group} = {{")
        out.append("\\tvalue = 0")
        for law in by_group[group]:
            lid = law["id"]
            out.append(f"\\tif = {{ limit = {{ owner = {{ has_law = law_type:{lid} }} }} add = sg_bpm_stance_{lid} }}")
        out.append("}")
        out.append("")''')
    text = replace_once(text, '        out.append(f"\\tadd = {{ value = sg_law_politics_{lid} }}")\n', '')
    text = replace_once(text, 'multiply = 0.5 }}"\n        )',
                        'multiply = 2 }}"\n        )\n        out.append(f"\\t\\tadd = sg_law_politics_{lid}")')
    text = replace_once(text, 'out.append("\\tmax = 200")', 'out.append("\\tmax = 450")')
    text, count = re.subn(r'weeks_until_bankruptcy < (26|52)',
                          r'net_total_income < 0 gold_reserves < { value = net_total_income multiply = -\1 }', text)
    if count != 2:
        raise ValueError('Fórmula fiscal do gerador mudou.')
    path.write_text(guard_ranking(text), encoding='utf-8')


def update_score_labels(stage):
    labels = {
        'braz_por': (
            'Balanço de apoio',
            'As três melhores reformas disponíveis são reavaliadas mensalmente. '
            'Para entrar na lista, a reforma precisa poder tramitar e melhorar o mérito da lei vigente.',
            'O ranking combina benefício, metade do risco, o dobro da chance inicial em pontos percentuais '
            'e a mudança de apoio dos grupos influentes em relação à lei vigente.',
            'de chance inicial × 2',
        ),
        'english': (
            'Net change in support',
            'The three highest-ranked available reforms are reviewed monthly. '
            'A reform must be eligible to start and improve on the current law.',
            'The ranking combines benefit, half the risk, twice the initial chance in percentage points '
            'and how influential groups view the reform compared with the current law.',
            'initial chance × 2',
        ),
    }
    for language, (support, header, tooltip, chance) in labels.items():
        path = stage / f'localization/{language}/sg_l_{language}.yml'
        text = path.read_text(encoding='utf-8-sig')
        for key, label in (('sg_header', header), ('sg_header_tt', tooltip),
                           ('sg_support_label', support + ':')):
            text = re.sub(rf'(?m)^ {key}:0 .*$', f' {key}:0 "{label}"', text)
        for slot in (1, 2, 3):
            value = f"[JournalEntry.GetCountry.MakeScope.Var('sg_top_{slot}_enactment_chance').GetValue|0]"
            text = re.sub(
                rf'(?m)^ (sg_why_ranked_{slot}:0 .*?) \+ (?:metade de|half of) {re.escape(value)}%[^"]*',
                lambda match: ' ' + match[1].replace('de apoio do governo', 'de balanço de apoio')
                .replace('government support', 'net change in support') + f' + {value}% {chance}.',
                text,
            )
        path.write_text(text, encoding='utf-8-sig')


def write_package(stage, output, name, meta):
    descriptor = f'name="{name}"\nversion="{meta["version"]}"\nsupported_version="{meta["supported_game_version"]}"\n'
    files = {
        f'{name}.mod': (descriptor + f'path="mod/{name}"\n').encode(),
        f'{name}/descriptor.mod': descriptor.encode(),
        f'{name}/.metadata/metadata.json': (json.dumps(meta, indent=2) + '\n').encode(),
    }
    for folder in RUNTIME:
        for path in (stage / folder).rglob('*'):
            if path.is_file():
                files[f'{name}/{path.relative_to(stage).as_posix()}'] = path.read_bytes()
    output.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(output, 'w', compression=ZIP_DEFLATED) as archive:
        for member, data in sorted(files.items()):
            info = ZipInfo(member, date_time=(2026, 11, 15, 0, 0, 0))
            info.compress_type = ZIP_DEFLATED
            archive.writestr(info, data)


def package(source, game, bpm, output):
    bpm_meta = json.loads((bpm / '.metadata/metadata.json').read_text(encoding='utf-8-sig'))
    if bpm_meta['id'] != BPM_ID:
        raise ValueError('A pasta informada não é a do Better Politics Mod.')
    with TemporaryDirectory(prefix='sg-bpm-') as temporary:
        stage = Path(temporary) / 'advisor'
        inputs = Path(temporary) / 'database'
        for folder in (*RUNTIME, 'tools', 'data'):
            shutil.copytree(source / folder, stage / folder, ignore=shutil.ignore_patterns('__pycache__'))
        shutil.copyfile(source / 'Smart Government Advisor.mod', stage / 'Smart Government Advisor.mod')
        make_database(game, bpm, inputs)
        adapt_generator(stage / 'tools/build_law_data.py')
        (stage / 'common/script_values/sg_rank_fallbacks.txt').write_text(
            score_fallbacks(), encoding='utf-8-sig')
        for script, args in (
            ('build_law_data.py', ['--game', str(inputs), '--out', str(stage)]),
            ('build_gui.py', []),
            ('validate.py', ['--game', str(inputs)]),
        ):
            subprocess.run([sys.executable, str(stage / 'tools' / script), *args], check=True)
        for path in [stage / 'gui/journal_entry_widgets/sg_law_advisor.gui',
                     *stage.glob('localization/*/sg_generated_l_*.yml')]:
            text = path.read_text(encoding='utf-8-sig')
            path.write_text(re.sub(r'\bsg_law_name_191\b', 'sg_bpm_law_name_191', text),
                            encoding='utf-8-sig')
        update_score_labels(stage)
        meta = json.loads((source / '.metadata/metadata.json').read_text(encoding='utf-8-sig'))
        meta.update(name=NAME, id='sg.smart_government_advisor_bpm', version='1.0.1',
                    relationships=[{'rel_type': 'dependency', 'id': BPM_ID,
                                    'display_name': bpm_meta['name'], 'resource_type': 'mod',
                                    'version': bpm_meta['version']}])
        write_package(stage, output, NAME, meta)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--government', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--game', required=True, type=Path)
    parser.add_argument('--bpm', required=True, type=Path)
    parser.add_argument('--output', type=Path, default=Path('dist/smart-government-advisor-bpm.zip'))
    args = parser.parse_args()
    print(package(args.government, args.game, args.bpm, args.output))
