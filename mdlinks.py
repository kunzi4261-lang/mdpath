"""Extract common single-line Markdown link targets without third-party modules.

Handles inline links, images and single-line reference definitions, including
angle-bracket destinations, nested parentheses, optional titles and escapes.
Reference definitions are reported once, on their own line, even if unused.
Skips top-level fenced code, indented lines and same-line code spans. This
line-oriented subset excludes HTML parsing, multiline links or code spans,
and code fences nested inside block quotes or list containers.
"""

import html
import re
import string
from typing import Iterator


FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
DEFINITION = re.compile(r"^ {0,3}\[(?:\\.|[^\[\]\\])+\]:[ \t]*")
TITLE = re.compile(r"""(?:"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|\((?:\\.|[^()\\])*\))""")
ESCAPE = re.compile(r"\\([" + re.escape(string.punctuation) + r"])")
ENTITY = re.compile(r"&(?:#[0-9]+|#[xX][0-9a-fA-F]+|[a-zA-Z][a-zA-Z0-9]+);")
TICKS = re.compile(r"`+")


def _spaces(line, index):
    while index < len(line) and line[index] in " \t":
        index += 1
    return index


def _destination(line, start):
    """Return a raw destination and the index after it, or None."""
    angled = line.startswith("<", start)
    index = start + int(angled)
    depth = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line) and line[index + 1] in string.punctuation:
            index += 2
            continue
        if angled:
            if char == ">":
                return line[start + 1:index], index + 1
            if char == "<":
                return None
        elif char in " \t" or (char == ")" and depth == 0):
            break
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
        index += 1
    if not angled and depth == 0:
        return line[start:index], index
    return None


def _target(line, start, *, definition=False):
    start = _spaces(line, start)
    parsed = _destination(line, start)
    if parsed is None:
        return None
    raw, end = parsed
    if definition and start == end:
        return None
    tail = _spaces(line, end)
    title = TITLE.match(line, tail) if tail > end else None
    if title:
        tail = _spaces(line, title.end())
    if definition:
        if tail != len(line):
            return None
    elif not line.startswith(")", tail):
        return None
    value = re.sub(
        ESCAPE.pattern + "|" + ENTITY.pattern,
        lambda match: match[1] if match[1] is not None else html.unescape(match[0]),
        raw,
    )
    return value, tail if definition else tail + 1


def _inline_targets(line):
    # A closing backtick run must match the opening run's length exactly.
    next_run = {}
    code_ends = {}
    for run in reversed(list(TICKS.finditer(line))):
        length = run.end() - run.start()
        code_ends[run.start()] = next_run.get(length, run.end())
        next_run[length] = run.end()

    index = 0
    open_brackets = 0
    while index < len(line):
        char = line[index]
        if char == "\\" and index + 1 < len(line) and line[index + 1] in string.punctuation:
            index += 2
            continue
        if char == "`" and index in code_ends:
            index = code_ends[index]
            continue
        if char == "[":
            open_brackets += 1
        elif char == "]" and open_brackets:
            open_brackets -= 1
            if line.startswith("(", index + 1):
                target = _target(line, index + 2)
                if target is not None:
                    value, index = target
                    yield value
                    continue
        index += 1


def iter_links(text: str) -> Iterator[tuple[int, str]]:
    """Yield (one-based source line, unescaped destination) in source order."""
    fence = ""
    for number, line in enumerate(text.splitlines(), start=1):
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1].startswith(fence) and not marker[2].strip():
                fence = ""
            continue
        if marker and (marker[1][0] == "~" or "`" not in marker[2]):
            fence = marker[1]
            continue
        if line.startswith(("    ", "\t")):
            continue
        definition = DEFINITION.match(line)
        if definition:
            target = _target(line, definition.end(), definition=True)
            if target is not None:
                yield number, target[0]
                continue
        for value in _inline_targets(line):
            yield number, value
