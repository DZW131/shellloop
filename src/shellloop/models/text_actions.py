"""Parse exactly one textual shell action out of model text.

The offline scripted model already returns structured actions, but a real
model will answer with free text.  The convention used here: the model puts
the shell command it wants to run into exactly one fenced code block.  This
module extracts that command as a pure function, without calling any model
and without modifying the original text, so the raw model output can still
be written to the trajectory unchanged.
"""

from __future__ import annotations

import re

from shellloop.core import Action

# A fence starts at the beginning of a line: ``` followed by an optional
# language tag and nothing else until the end of that line.  The tag must be
# one of the shell variants below; any other tag is rejected explicitly.
_OPEN_RE = re.compile(r"^```([a-zA-Z0-9_+-]*)[ \t]*$")
_CLOSE_RE = re.compile(r"^```[ \t]*$")

_ALLOWED_TAGS = ("", "bash", "sh", "shell")


class TextActionFormatError(ValueError):
    """Raised when the model text does not contain exactly one non-empty code block."""


def parse_text_actions(text: str) -> list[Action]:
    """Extract exactly one shell command from *text*.

    Returns a single-element action list, e.g. ``[{"command": "ls -la"}]``.

    Raises:
        TextActionFormatError: if there is no code block, more than one code
            block, the single code block is empty or blank, the language tag
            is not one of bash/sh/shell, or an opening fence is not followed
            by a newline.
    """
    blocks = _collect_blocks(text)
    if not blocks:
        raise TextActionFormatError("no fenced code block found in model text")
    if len(blocks) > 1:
        raise TextActionFormatError(f"expected exactly one fenced code block, found {len(blocks)}")
    command = blocks[0].strip()
    if not command:
        raise TextActionFormatError("fenced code block is empty")
    return [{"command": command}]


def _collect_blocks(text: str) -> list[str]:
    """Return the contents of every well-formed fenced code block in *text*.

    Fences are parsed line by line so that the language tag is validated
    explicitly and the fence itself must end at its own line.
    """
    blocks: list[str] = []
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.startswith("```"):
            i += 1
            continue
        match = _OPEN_RE.match(line)
        if match is None:
            # A fence-looking line with trailing content, e.g. "```bash echo".
            raise TextActionFormatError("invalid fenced code block: opening fence must be followed by a newline")
        tag = match.group(1)
        if tag not in _ALLOWED_TAGS:
            raise TextActionFormatError(f"unsupported language tag in fenced code block: {tag!r}")
        content: list[str] = []
        i += 1
        while i < len(lines) and not _CLOSE_RE.match(lines[i]):
            content.append(lines[i])
            i += 1
        if i >= len(lines):
            raise TextActionFormatError("unclosed fenced code block")
        blocks.append("\n".join(content))
        i += 1
    return blocks
