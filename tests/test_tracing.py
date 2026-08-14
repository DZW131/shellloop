from shellloop.tracing import assistant_preview, command_preview, safe_preview


def test_safe_previews_redact_credentials_and_bound_text():
    assert safe_preview("Authorization: Bearer abcdefghijklmnop") == "Authorization: Bearer ***"
    assert safe_preview("token=very-secret-value") == "token=***"
    assert safe_preview("sk-1234567890abcdef") == "key-***"
    assert command_preview("  echo   hello  ") == "echo hello"
    assert safe_preview("x" * 700).endswith("...")
    assert len(safe_preview("x" * 700)) == 600


def test_assistant_preview_keeps_visible_plan_but_separates_the_action():
    preview = assistant_preview("Plan: inspect files.\n```bash\nls -la\n```")

    assert "Plan: inspect files." in preview
    assert "ls -la" not in preview
    assert "shell action shown separately" in preview
