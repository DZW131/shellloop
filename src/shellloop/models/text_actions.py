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

# Matches fenced code blocks whose fence is at the start of a line.
# The language tag is optional and, when present, must be bash/sh/shell.
# Longer alternatives come first so "shell" is not split by "sh".
_FENCE_RE = re.compile(r"^```(?:bash|shell|sh)?[ \t]*\n?(.*?)^```[ \t]*$", re.MULTILINE | re.DOTALL)


class TextActionFormatError(ValueError):
    """Raised when the model text does not contain exactly one non-empty code block."""


def parse_text_actions(text: str) -> list[Action]:
    """Extract exactly one shell command from *text*.

    Returns a single-element action list, e.g. ``[{"command": "ls -la"}]``.

    Raises:
        TextActionFormatError: if there is no code block, more than one code
            block, or the single code block is empty or blank.
    """
    blocks = _FENCE_RE.findall(text)
    if not blocks:
        raise TextActionFormatError("no fenced code block found in model text")
    if len(blocks) > 1:
        raise TextActionFormatError(f"expected exactly one fenced code block, found {len(blocks)}")
    command = blocks[0].strip()
    if not command:
        raise TextActionFormatError("fenced code block is empty")
    return [{"command": command}]
