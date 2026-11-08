"""Minimal Clausewitz script parser for Victoria 3 law files."""
from __future__ import annotations
import re
from dataclasses import dataclass

TOKEN_RE = re.compile(r'"(?:[^"\\]|\\.)*"|[{}]|\?=|<=|>=|!=|[=<>]|[^\s{}=<>"]+')


def strip_comments(text: str) -> str:
    out = []
    in_str = False
    esc = False
    for ch in text:
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == '\\':
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
        elif ch == '#':
            # skip to end of line
            while out and out[-1] in ' \t':
                out.pop()
            break
        else:
            out.append(ch)
        if ch == '\n':
            continue
    # The loop above drops newlines while skipping comments; rebuild is unnecessary
    # because tokens are whitespace-insensitive. Re-run line-wise for correctness.
    lines = []
    for line in text.splitlines():
        in_str = False
        esc = False
        buf = []
        for ch in line:
            if in_str:
                buf.append(ch)
                if esc:
                    esc = False
                elif ch == '\\':
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
                buf.append(ch)
            elif ch == '#':
                break
            else:
                buf.append(ch)
        lines.append(''.join(buf))
    return '\n'.join(lines)


def tokenize(text: str):
    text = strip_comments(text)
    for m in TOKEN_RE.finditer(text):
        tok = m.group(0)
        yield tok


class Parser:
    def __init__(self, text: str):
        self.tokens = list(tokenize(text))
        self.i = 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def pop(self):
        t = self.tokens[self.i]
        self.i += 1
        return t

    def parse(self):
        items = []
        while self.i < len(self.tokens):
            key = self.pop()
            if key == '}':
                continue
            if key == '{' or key in ('=', '?=', '<', '>', '<=', '>=', '!='):
                # malformed; skip
                continue
            if self.peek() in ('=', '?=', '<', '>', '<=', '>=', '!='):
                op = self.pop()
                val = self.parse_value()
                items.append((key, op, val))
            elif self.peek() == '{':
                self.pop()
                val = self.parse_block()
                items.append((key, None, val))
            else:
                items.append((key, None, None))
        return items

    def parse_value(self):
        t = self.pop()
        if t == '{':
            return self.parse_block()
        return t

    def parse_block(self):
        items = []
        while self.i < len(self.tokens):
            if self.peek() == '}':
                self.pop()
                break
            key = self.pop()
            if key == '}':
                break
            if self.peek() in ('=', '?=', '<', '>', '<=', '>=', '!='):
                op = self.pop()
                val = self.parse_value()
                items.append((key, op, val))
            elif self.peek() == '{':
                self.pop()
                val = self.parse_block()
                items.append((key, None, val))
            else:
                items.append((key, None, None))
        return items


def parse(text: str):
    return Parser(text).parse()


def to_dict(items):
    """Convert parsed list to dict; repeated keys become lists. Keeps only first op per key."""
    d = {}
    for key, op, val in items:
        if isinstance(val, list):
            val = to_dict(val)
        if key in d:
            if not isinstance(d[key], list):
                d[key] = [d[key]]
            d[key].append(val)
        else:
            d[key] = val
    return d


def get(d, key, default=None):
    v = d.get(key, default)
    if isinstance(v, list) and v and isinstance(v[0], dict):
        # ambiguous; return last
        return v[-1]
    return v
