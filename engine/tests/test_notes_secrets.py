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


# Shapes a sprinter building a product pastes all the time.
@pytest.mark.parametrize("raw, expected", [
    ("DATABASE_URL=postgres://admin:S3cretPass99@db.example.com:5432/app",
     "DATABASE_URL=postgres://admin:[removed]@db.example.com:5432/app"),
    ("mongodb+srv://vic:hunter2xyz@cluster0.abcde.mongodb.net/test",
     "mongodb+srv://vic:[removed]@cluster0.abcde.mongodb.net/test"),
    ("redis://:p4ssw0rd@localhost:6379", "redis://:[removed]@localhost:6379"),
    ("Authorization: Bearer abcDEF123456ghiJKL7890", "Authorization: Bearer [removed]"),
    ("curl -H 'Authorization: Basic dXNlcjpwYXNz' https://api.example.com",
     "curl -H 'Authorization: Basic [removed]' https://api.example.com"),
    ("send it with bearer 9f8e7d6c5b4a39281706", "send it with bearer [removed]"),
    ("sk_live_" + "4eC39HqLyjWDarjtT1zdp7dc" + "AbCdEfGh", "[removed]"),
    ("STRIPE_KEY=sk_test_" + "a1B2c3D4" * 4, "STRIPE_KEY=[removed]"),
    ("rk_live_" + "Zx9" * 8, "[removed]"),
    ("maps key AIza" + "SyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY" + " thanks", "maps key [removed] thanks"),
    ("AWS_ACCESS_KEY=abc123def", "AWS_ACCESS_KEY=[removed]"),
])
def test_redacts_common_paste_shapes(raw, expected):
    assert redact(raw) == expected


@pytest.mark.parametrize("s", [
    "first clinic signed, €200/month — we talked to 12 clinics",
    "the secret: customers want sync",
    "our token: an hour with the founder",
    "the bearer of bad news was the pilot clinic",
    "bearer bonds are not our market",
    "see https://example.com:8080/docs/pricing@v2 for the plan",
    "we met at https://clinic.example.com/about and they asked for 3 seats",
    "the key: clinics hate double-booking",
    "monkey: business as usual, 40 sign-ups",
    "Authorization flows took us two weeks",
])
def test_ordinary_story_text_survives(s):
    assert redact(s) == s


@pytest.mark.parametrize("raw", ["secret: hunter2xyz9", "token: 9f8e7d6c5b4a", "secret = s3cr3t", "password: hunter2"])
def test_secret_and_token_still_go_when_the_value_looks_like_one(raw):
    out = redact(raw)
    assert out.endswith("[removed]") and not any(c.isdigit() for c in out)
