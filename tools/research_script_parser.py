"""Small structural parser for the subset used by this mod; not an engine validator."""

from dataclasses import dataclass
import re


TOKEN = re.compile(r'\s+|#[^\n]*|"(?:\\.|[^"\\])*"|[{}]|\?=|>=|<=|!=|[=<>]|[^\s{}=<>!?#"]+')


@dataclass
class Entry:
    key: str
    op: str | None
    value: object


def parse(text):
    tokens = []
    position = 0
    text = text.lstrip('\ufeff')
    for match in TOKEN.finditer(text):
        if match.start() != position:
            raise ValueError(f'Unrecognized token at offset {position}')
        position = match.end()
        token = match.group()
        if not token.isspace() and not token.startswith('#'):
            tokens.append(token)
    if position != len(text):
        raise ValueError(f'Unrecognized token at offset {position}')
    cursor = 0

    def scalar(token):
        return token[1:-1] if token.startswith('"') else token

    def block(nested=False):
        nonlocal cursor
        result = []
        while cursor < len(tokens):
            key = tokens[cursor]
            cursor += 1
            if key == '}':
                if not nested:
                    raise ValueError('Unexpected closing brace')
                return result
            if key in ('{', '=', '<', '>', '>=', '<=', '!=', '?='):
                raise ValueError('Unexpected token ' + key)
            op = None
            value = None
            if cursor < len(tokens) and tokens[cursor] in ('=', '<', '>', '>=', '<=', '!=', '?='):
                op = tokens[cursor]
                cursor += 1
                if cursor == len(tokens) or tokens[cursor] == '}':
                    raise ValueError('Missing value for ' + key)
                value = tokens[cursor]
                cursor += 1
                if value == '{':
                    value = block(True)
                else:
                    value = scalar(value)
                    if cursor < len(tokens) and tokens[cursor] == '{':
                        cursor += 1
                        value = [Entry('type_name', None, value)] + block(True)
            elif cursor + 1 < len(tokens) and tokens[cursor + 1] == '{':
                # GUI declarations such as `types name { ... }` use an
                # implicit named block instead of an equals sign.
                value = [Entry('name', None, scalar(tokens[cursor]))]
                cursor += 2
                value.extend(block(True))
            result.append(Entry(scalar(key), op, value))
        if nested:
            raise ValueError('Unclosed block')
        return result

    return block()


def walk(entries):
    for entry in entries:
        yield entry
        if isinstance(entry.value, list):
            yield from walk(entry.value)


def child(entries, key):
    return next(entry.value for entry in entries if entry.key == key)
