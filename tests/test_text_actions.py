import pytest

from shellloop.models.text_actions import TextActionFormatError, parse_text_actions


def test_parses_single_fenced_command():
    text = "I will list the files:\n```bash\nls -la\n```"
    assert parse_text_actions(text) == [{"command": "ls -la"}]


def test_accepts_bare_fence_without_language():
    assert parse_text_actions("```\necho hello\n```") == [{"command": "echo hello"}]


def test_accepts_sh_and_shell_language_tags():
    assert parse_text_actions("```sh\npwd\n```") == [{"command": "pwd"}]
    assert parse_text_actions("```shell\ndate\n```") == [{"command": "date"}]


def test_keeps_multiline_command_body():
    text = "```bash\ncd /tmp\ntouch marker\n```"
    assert parse_text_actions(text) == [{"command": "cd /tmp\ntouch marker"}]


def test_rejects_text_without_code_block():
    with pytest.raises(TextActionFormatError):
        parse_text_actions("This is just a plain sentence with no fence.")


def test_rejects_multiple_code_blocks():
    text = "```bash\necho one\n```\n```bash\necho two\n```"
    with pytest.raises(TextActionFormatError):
        parse_text_actions(text)


def test_rejects_empty_code_block():
    with pytest.raises(TextActionFormatError):
        parse_text_actions("```\n```")


def test_rejects_whitespace_only_code_block():
    with pytest.raises(TextActionFormatError):
        parse_text_actions("```bash\n   \n```")


def test_leaves_original_text_untouched():
    text = "```bash\nls\n```"
    before = text
    parse_text_actions(text)
    assert text == before
