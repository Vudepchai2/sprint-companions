# Memory: the sprinter's second brain

Each sprinter has one **memory bank**, shared by all four companions: a folder under `<home>/people/`. It holds what they've told you and what they typed while building, in their words. You read it to avoid asking twice and to ask better; you never read it back as a script. Everything stays on this machine. (`<home>` is the data folder: `~/SprintCompanions`, or `COMPANIONS_HOME` if that's set.)

`companions bank --ensure` prints the bank folder. Commands are `companions memory <command>`, where `<bank>` is that folder. Put paths in double quotes:
- `companions memory brief "<bank>"`: a short read of who they are, how they tell it, their moments in date order, people, occasions, open conflicts and gaps. A claim whose status isn't `said` shows it, as in `monthly_price=200 EUR per month (corroborated)`. Run it after every catch-up.
- `companions memory gaps "<bank>"`: what the bank is missing, as JSON. Each gap names the `question_section` of `questions.md` to draw on.
- `companions memory recall "<bank>" [--query <words>] [--about <id>] [--entity <name>] [--type <type>] [--since <date>] [--limit <n>]`: look things up before you ask or add. Each record shows its `sources`, with `kind`, `ref`, `at` and `by`, and its `status`.
- `companions memory retain "<bank>" -`: write what you learned, with the batch on stdin (below).
- `companions memory import "<bank>" "<file>"`: copy a document in and register it. It prints a source id such as `s1`.
- `companions memory pages "<bank>"`: rewrite the readable pages in `<bank>/pages/`.
- `companions memory forget "<bank>" <id> --reason "<why>"`: retract one record.
- `companions memory delete "<bank>" --yes`: remove the whole bank. Only on their explicit request, after confirming.
- `companions memory demo-brief "<bank>" "<plan.json>"`: render the demo-day brief. `/brief` uses it.

## The session ref
Every retain from a conversation uses the ref `sessions/${CLAUDE_SESSION_ID}`, with the session id your `SKILL.md` printed. It matches the `session` that quiet notes keep for this conversation, so a number digested from this conversation's notes and then said again live stays one source.

If that id is empty or still reads as a placeholder, use `sessions/<session>`, where `<session>` is the one you noted at catch-up: the newest entry for the folder you're running in, from the first `companions notes read`, before `notes done` took it out. If you noted none (quiet notes aren't on, or this folder isn't the startup), use `sessions/day-<YYYY-MM-DD>`, such as `sessions/day-2026-11-23`. That is the same form catch-up uses for notes with an empty `session`. It makes one source per day, which errs toward under-counting corroboration.

Use the same ref for the whole conversation, whichever companion is speaking. One conversation is one source, so a number said twice in it doesn't count as corroborated.

## When to retain
1. **After each answer that gives you a moment, a person, a number or a meaning:** retain it before your next question. Source: `said`, with `"by"` set to your code.
2. **At catch-up:** one batch per quiet-notes session, as `base.md` says. Source: `build`, with `"by": "notes"` and the ref `sessions/<session>` from the notes.
3. **For demo day:** the occasion, with its `date`, `format` and `audience`, each in the sprinter's words. Source: `said`.
4. **From a document:** `import` it, then retain what it says with a `document` source whose `ref` is the source id. Imported moments stay "imported" until they tell them in their own words.
5. **Your own reading** of a thread across moments: an observation with a `companion` source (see Reflect).

Retain in small batches, one cluster at a time. Never retain for the sake of it: no answer, no record.

## The batch shape
A batch is one JSON object: a single `source` and a list of `items`. Pass it on stdin, in a quoted heredoc, so nothing is written to disk and nothing lands in the folder Claude Code was started in. The whole batch is checked first, and one error rejects all of it (the messages name the item).

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "said", "ref": "sessions/${CLAUDE_SESSION_ID}", "at": "2026-11-23", "by": "ks"},
  "items": [ ... ]
}
EOF
```

- `source.kind` is one of `said` (they told you), `build` (what they typed while building, from quiet notes), `document` (an imported file; `ref` must be its source id, like `s1`) or `companion` (your own reading). `ref` is required and says where it came from. `at` is the date. A `build` source also has `project`, the last path part of the notes' folder, such as `clinic-app`.
- `source.by` says who was speaking when it was retained: `tt`, `ks`, `mm` or `mr` for a companion, or `notes` for quiet notes. Always set it.
- `build` counts as the sprinter's own words: its moments are "told", and its claims count toward corroboration like `said` ones. A claim is corroborated only when the same number comes from two different refs (two different sessions). The same session saying it twice is still one source.
- Each item is `{"op": ..., ...}`. `op` defaults to `add`. The ops are `add`, `update`, `confirm`, `retract`, `cite` and `resolve`.
- `add` needs a `type`:
  - `entity`: `name`, `kind` (person, org, place, event, project or other); optional `aliases`, `relation`.
  - `moment`: `title`, `what_happened`; optional `when`, `date`, `where`, `who`, `what_changed`, `meaning`, `quotes`.
  - `claim`: `about`, `key`, `statement`, `quote`; optional `value`, `unit`.
  - `observation`: `about`, `statement`; optional `evidence`, `moments`.
  - `occasion`: `name`; optional `"format"` (the pitch format in their words, such as "3-minute pitch with slides, no Q&A"), `audience`, `date`, `session`, `uses`, `outcome`, `debrief`.
- Text fields are strings. `aliases`, `quotes` and `debrief` (their words about how it went) are lists of strings. `value` is a number (`200`, never `"200"`). `evidence` is a list of `{"ref": ..., "quote": ...}`. A `date` is `YYYY`, `YYYY-MM` or `YYYY-MM-DD`.
- Give an item a `ref` of your choosing, starting with `@` (for example `"ref": "@signed"`), and later items in the same batch can use it: `"about": "@signed"`, `"who": ["@clinic"]`. Outside the batch, use the ids the report gives back (`m1`, `e2`).
- `who` takes entity names or ids. `moments` and `uses` take moment ids or `@handles`.
- A claim's `about` is a moment, entity or occasion id (or `@handle`). An observation's `about` is the literal word `person` or `telling`, never an id.
- `update` takes `id` and `fields`. A name or a number never changes by update: a changed number is a new claim.
- `confirm` takes `id` and `quote`, and `resolve` takes `conflict`, `keep` and `quote`. Both need a `said` source.
- `retract` takes `id` and `reason`.

Run `retain` and read the report. It lists what was `added` (with ids), which names were `linked` to an existing entity (with that entity's `kind` and `relation`), which claims were `cited` (the same number said again; it corroborates only when the new source has a different ref, which means a different session), any `conflicts`, and `keys_by_about`, the claim keys already used for each thing.

### Worked example
The sprinter is building a booking app for clinics, in the folder `clinic-app`. At catch-up, one quiet-notes session holds three prompts: "add a cancel button to the booking form", "first clinic signed, €200/month, they want it synced with their booking system" and "fix the failing test in billing.py". Only the middle one is story material:

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "build", "ref": "sessions/4f2a9c1e", "at": "2026-11-18", "by": "notes", "project": "clinic-app"},
  "items": [
    {"type": "entity", "ref": "@clinic", "name": "First clinic", "kind": "org",
     "relation": "the first clinic to sign up"},
    {"type": "moment", "ref": "@signed", "title": "First clinic signed",
     "date": "2026-11-18", "who": ["@clinic"],
     "what_happened": "The first clinic signed up, at €200 a month, and asked for a sync with their booking system.",
     "quotes": ["first clinic signed, €200/month, they want it synced with their booking system"]},
    {"type": "claim", "about": "@signed", "key": "monthly_price", "statement": "The first clinic pays €200 a month.",
     "value": 200, "unit": "EUR per month", "quote": "first clinic signed, €200/month"}
  ]
}
EOF
```

A week later the sprinter tells KS: "the first clinic pays 150 a month after the pilot discount". Retain it with a `said` source and the same key. Look at `keys_by_about` from the last report, or `recall`, so you reuse `monthly_price` rather than inventing `price_per_month`:

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "said", "ref": "sessions/${CLAUDE_SESSION_ID}", "at": "2026-11-25", "by": "ks"},
  "items": [
    {"type": "claim", "about": "m1", "key": "monthly_price", "statement": "The first clinic pays €150 a month.",
     "value": 150, "unit": "EUR per month", "quote": "the first clinic pays 150 a month after the pilot discount"}
  ]
}
EOF
```

Same key, different number: the report shows a conflict (`x1`, between `c1` and `c2`), and both claims show as conflicted until it's resolved. Ask once (below). The sprinter answers "150 during the pilot, 200 from March." Both are true, but they count different things. Retain the second as its own claim, with a key from their words, and resolve the conflict with a `said` source and their quote:

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "said", "ref": "sessions/${CLAUDE_SESSION_ID}", "at": "2026-11-25", "by": "ks"},
  "items": [
    {"type": "claim", "about": "m1", "key": "price_from_march", "statement": "From March the first clinic pays €200 a month.",
     "value": 200, "unit": "EUR per month", "quote": "150 during the pilot, 200 from March."},
    {"op": "resolve", "conflict": "x1", "keep": "c2",
     "quote": "150 during the pilot, 200 from March."}
  ]
}
EOF
```

Then the sprinter tells MM about demo day. The audience goes on the occasion, in their words:

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "said", "ref": "sessions/${CLAUDE_SESSION_ID}", "at": "2026-11-25", "by": "mm"},
  "items": [
    {"type": "occasion", "ref": "@demo", "name": "Demo day", "date": "2026-12-12",
     "format": "3-minute pitch with slides, no Q&A",
     "audience": "seed investors and corporates, they care about paying customers"}
  ]
}
EOF
```

**A number under a different key.** Later the sprinter says "we've got 3 clinics on the pilot". That isn't the same as one signed clinic, so don't file it under an existing key: that would decide for them that a pilot is a sale. Retain it under a key from their words, such as `pilot_clinics`. The engine only catches a different number under the same key, so it reports nothing. Spotting a mismatch across keys is your job in Reflect. Retain your reading as a `telling` observation, then ask about it once with a question from `Recall: checking a number`:

```
companions memory retain "<bank>" - <<'EOF'
{
  "source": {"kind": "companion", "ref": "sessions/${CLAUDE_SESSION_ID}", "at": "2026-11-26", "by": "ks"},
  "items": [
    {"type": "observation", "about": "telling", "moments": ["m1"],
     "statement": "The clinic count changes between tellings: one signed clinic in the notes, 3 clinics on the pilot now.",
     "evidence": [
       {"ref": "sessions/4f2a9c1e", "quote": "first clinic signed, €200/month"},
       {"ref": "sessions/${CLAUDE_SESSION_ID}", "quote": "we've got 3 clinics on the pilot"}]}
  ]
}
EOF
```

## Rules
- **Quote their words verbatim.** Every claim carries the exact words they used or typed, short. Don't tidy or paraphrase a quote.
- **Never invent or round a number.** If they said "about a hundred", the value is not 100 and you can ask. If you don't have a number, there is no claim.
- **Check before you add an entity.** Run `recall` or `brief` first. Adding a name that is already known links to it and adds an alias. A name that already belongs to a different entity is rejected.
- **Read every `linked` entry.** If its `kind` or `relation` doesn't fit, the name belongs to someone else (two clinics both called "the clinic"). Undo the link: add the new one again with a distinguishing name, `update` the `who` of any moment from that batch to the new id, and `update` the old entity's `aliases` if the link added one. Don't `forget` the old entity: it's real too.
- **Reuse the claim keys** listed in `keys_by_about`. A new key for a number they already gave hides a conflict.
- **The `companion` source is for observations only.** Anything you retain as your own reading is an observation. Facts come from the sprinter: `said`, `build` or `document`.
- **The audience: on the occasion, in the sprinter's words.** The demo-day audience is described only on the occasion's `audience`, the way the sprinter describes it. There are no records about named individuals in the audience, no research on anyone, and no judgements of your own.
- **People in the story** (a cofounder, the first clinic): a name, a role and their part in the story, as the sprinter told it. Nothing else.
- **Quiet notes keep only what the sprinter typed.** Retain story material from them; never Claude's replies, code or coding instructions.
- **Write only what is true to their words.** No diagnosis, and no emotions read into them.

## A conflict between two numbers
When `retain` reports a conflict, or `brief` or `gaps` shows an open one:
1. Ask once, as the turn's one question, using the section `Recall: checking a number` in `questions.md`. Give both numbers and where each came from, in their words, and ask which is right or how they fit.
2. Don't pick. Don't average. Don't bring it up again once it's resolved.
3. When they answer, `resolve` with `keep` set to the claim that stands and their answer as the `quote`. If both are true in different ways ("150 during the pilot, 200 from March"), retain the second as its own claim with a different key from their words, then resolve to whichever they say the story should use.

## Reflect
After every few moments (about every third), look across the bank for threads: a customer who keeps coming up, a kind of turn they always tell, a claim they never back with a scene, a belief that shows up in two stories.
- Look for **numbers under different keys that may count the same thing** (one signed clinic and 3 pilot clinics; 40 sign-ups and 12 active users). The engine only flags a changed number under the same key, so these are yours to spot. Retain the mismatch as a `telling` observation and raise it once with the `Recall: checking a number` questions, as in the worked example.
- Retain each thread as an observation with a `companion` source, `about` `person` (about them) or `telling` (about how they tell it), and `moments` set to the moments it rests on.
- Present it as **the companion's reading**, never as fact: say what you noticed, name the moments, and ask if it fits (the question section is `Recall: connecting moments`). It stays labelled as a reading until they confirm it.
- When they confirm, `confirm` it with a `said` source and their words as the quote. When they say it's wrong, `retract` it with their reason.

## Their bank, their say
Tell them once, early, that the pages in `<bank>/pages/` are theirs to read. They can correct anything through you (add a corrected claim, or `retract`), `forget` a record, `delete` the bank, or turn quiet notes off with `companions notes off`. Do it when they ask; confirm before `delete`.
