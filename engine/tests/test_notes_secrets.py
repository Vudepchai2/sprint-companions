import pytest

from companions.notes.secrets import redact


@pytest.mark.parametrize("raw", [
    "use sk-ant-api03-" + "a" * 40, "token ghp_" + "A" * 36, "github_pat_" + "b" * 30,
    "AKIA" + "ABCDEFGHIJKLMNOP", "xoxb-1234567890-abcdefghij",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop",
    "-----BEGIN OPENSSH PRIVATE KEY-----\nabc\n-----END OPENSSH PRIVATE KEY-----",
    "password: hunter2", "API_KEY=abc123", "secret = s3cr3t",
])
def test_redacts(raw):
    out = redact(raw)
    assert "[removed]" in out
    for frag in ("aaaaaaaaaa", "AAAAAAAAAA", "bbbbbbbbbb", "ABCDEFGHIJKLMNOP", "abcdefghij", "hunter2", "abc123", "s3cr3t"):
        assert frag not in out


def test_keeps_story_text():
    s = "first clinic signed, €200/month — we talked to 12 clinics"
    assert redact(s) == s


@pytest.mark.parametrize("raw, expected", [
    ("password: hunter2", "password: [removed]"),
    ("API_KEY=abc123 then more", "API_KEY=[removed] then more"),
    ("secret = s3cr3t", "secret = [removed]"),
])
def test_key_value_keeps_the_key_name(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize("raw, key, value_parts", [
    ("DB_PASSWORD=hunter2", "DB_PASSWORD", ["hunter2"]),
    ("OPENAI_API_KEY=abc123", "OPENAI_API_KEY", ["abc123"]),
    ("export GITHUB_TOKEN=abc123", "GITHUB_TOKEN", ["abc123"]),
    ("STRIPE_SECRET_KEY=abc123xyz", "STRIPE_SECRET_KEY", ["abc123", "xyz"]),
    ('{"password": "hunter2"}', "password", ["hunter2"]),
    ('password: "hunter 2"', "password", ["hunter", '2"']),
])
def test_redacts_identifier_and_quoted_forms(raw, key, value_parts):
    out = redact(raw)
    assert "[removed]" in out and key in out
    for part in value_parts:
        assert part not in out


@pytest.mark.parametrize("s", ["we burned 2000 tokens: worth it", "the secretary: Jane, from clinic 3"])
def test_plural_and_longer_words_are_not_keys(s):
    assert redact(s) == s


def test_private_key_block_is_removed_whole():
    raw = "here:\n-----BEGIN RSA PRIVATE KEY-----\nMIIabc\ndef\n-----END RSA PRIVATE KEY-----\nthanks"
    assert redact(raw) == "here:\n[removed]\nthanks"


def test_long_opaque_strings_are_removed():
    assert redact("blob " + "Zq9" * 20 + " end") == "blob [removed] end"
