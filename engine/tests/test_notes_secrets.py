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
    ("DATABASE_URL=postgres://admin:S3cretPass99@example.com:5432/app",
     "DATABASE_URL=postgres://admin:[removed]@example.com:5432/app"),
    ("mongodb+srv://founder:hunter2xyz@example.com/test",
     "mongodb+srv://founder:[removed]@example.com/test"),
    ("redis://:p4ssw0rd@localhost:6379", "redis://:[removed]@localhost:6379"),
    ("Authorization: Bearer abcDEF123456ghiJKL7890", "Authorization: Bearer [removed]"),
    ("Authorization: Bearer abcDEF123456ghiJKL7890. Then retry", "Authorization: Bearer [removed]. Then retry"),
    ("token it with bearer 9f8e7d6c5b4a3928, then", "token it with bearer [removed], then"),
    ("send it with bearer 9f8e7d6c5b4a3928.", "send it with bearer [removed]."),
    ("curl -H 'Authorization: Basic dXNlcjpwYXNz' https://api.example.com",
     "curl -H 'Authorization: Basic [removed]' https://api.example.com"),
    ("send it with bearer 9f8e7d6c5b4a39281706", "send it with bearer [removed]"),
    ("sk_live_" + "Fake0" * 4 + "Ab12", "[removed]"),  # 32 characters in all: under the 40-character catch-all
    ("STRIPE_KEY=sk_test_" + "a1B2c3D4" * 4, "STRIPE_KEY=[removed]"),
    ("rk_live_" + "Zx9" * 8, "[removed]"),
    ("maps key AIza" + "Sy" + "Fake-0_9x" * 3 + "Fake-0" + " thanks", "maps key [removed] thanks"),
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


@pytest.mark.parametrize("raw,want", [
    ("my API token: 3f9a1c2b4d5e6f708192a3b4c5d6e7f8, why does it 401?", "my API token: [removed], why does it 401?"),
    ("the secret: a8f3k2m9q1, keep it safe", "the secret: [removed], keep it safe"),
    ("secret: aB3$xY9!q", "secret: [removed]"),
    ("secret: hunter2", "secret: [removed]"),
    ("token: abc123", "token: [removed]"),
    ("the secret: aBcDeFgHiJ; keep it", "the secret: [removed]; keep it"),
    ("(token: x9y8z7)", "(token: [removed])"),
])
def test_bare_secret_and_token_values_go_whatever_their_shape(raw, want):
    assert redact(raw) == want


@pytest.mark.parametrize("s", [
    "the secret: customers want sync",
    "the secret: we listened",
    "token: of appreciation",
    "the secret: customers, not features",
])
def test_bare_secret_prose_with_plain_lowercase_word_survives(s):
    assert redact(s) == s


def test_long_dotted_run_redacts_fast():
    import time
    text = "a." * 10000
    start = time.perf_counter()
    redact(text)
    assert time.perf_counter() - start < 1.0
