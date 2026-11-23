---
name: brief
description: Use when the sprinter wants to prepare for demo day or another pitch: a draft script, the story, proof points, or who will be in the audience, or calls /brief.
allowed-tools: Bash(companions *), Read, Write
---

# Brief

This drafts the sprinter's demo-day script from their own memory, for all four companions. This session's id is `${CLAUDE_SESSION_ID}`.

1. Before you answer, read these files in full:
   - `${CLAUDE_SKILL_DIR}/../../references/base.md`: how every companion answers.
   - `${CLAUDE_SKILL_DIR}/../../references/memory.md`: the memory commands, batch shape and rules.
   - `${CLAUDE_SKILL_DIR}/../../references/questions.md`: the gap questions.
2. Catch up, following `## Before you answer: catch up` in `base.md`. Every reply starts with `Brief · <occasion name>`. A retain from here uses a `said` source, the ref `sessions/${CLAUDE_SESSION_ID}` (or the fallback in `memory.md`, "The session ref"), and `"by"` set to the code of the companion this conversation last spoke as, or `mm` if none has spoken.

## The occasion
3. Run `companions memory recall "<bank>" --type occasion --limit 50`. Use the occasion the sprinter names; if they name none, use `Demo day`. If it doesn't exist, retain it as a new `occasion` with `"name": "Demo day"` (or their name for it).
4. The plan needs its `date`, its `format` (the format and length, such as "3-minute pitch with slides, no Q&A") and its `audience` (who'll be there and what they care about). Ask for each missing one in its own turn, one question per turn, and keep their words. After each answer, retain it onto the occasion with `{"op": "update", "id": "<occasion id>", "fields": {"format": "<their words>"}}`. A `date` is `YYYY-MM-DD`; turn "next Friday" into one from today's date and say it back in the same reply.
5. The audience is described on the occasion, in the sprinter's words, and nowhere else. If they name people, keep only how they describe the room. No records about named individuals, no research on anyone, no judgement of your own.

## The plan
6. Read the material: `companions memory recall "<bank>" --type moment --limit 500` and `companions memory recall "<bank>" --type claim --limit 500`. You need the ids, the quotes and each claim's `status`.
7. **Choose the beats** from the moments and claims, in an order that suits the `format` and the `audience`: what the room cares about early, the customer scene that proves it, the numbers it rests on, the ask. Skip retracted records. Don't build a beat on a `conflicted` claim; ask the conflict question from `memory.md` first, as that turn's one question.
8. **Write each draft line in the sprinter's voice**, reusing their phrases from the quotes. A line is what they'd say on stage, not a summary of the record.
   - Size the script to the `format`, at 150 words per minute: a 3-minute pitch is about 450 words across all lines. If the format gives no length, ask for it before writing.
   - Every beat `cites` the moment or claim ids it rests on.
   - Every number in a line must come from a cited record: its title, what happened, statement, quote or value. Digits and number words both count: "three", "a dozen", "a hundred" and "one" are numbers too.
   - If a beat needs a number that memory doesn't have, don't write it: ask the sprinter for it, as that turn's one question, and retain the answer as a claim first.
9. **Pick the proof**: the claim ids that back the story. The page lists corroborated ones first and flags conflicts under `Conflicts to settle`; never leave a conflicted claim out to hide it.
10. **Add `before_stage`**: one question from each of up to three companions whose lens fits what's open, such as a conflict, a gap from `companions memory gaps "<bank>"` or a thin beat. `by` is `tt` (the bold move), `ks` (the money side), `mm` (the pitch and the honest check) or `mr` (the team and the evidence). Each is one question, in that companion's voice, with no invented number.
11. **Write the plan** with Write to `<bank>/brief-plan.json`, using the real bank folder. `occasion` is the occasion id, `script` is the beats in order, `proof` is a list of claim ids, and `before_stage` is the questions. For example, for the clinic story in `memory.md`:

```json
{
  "occasion": "oc1",
  "script": [
    {"line": "The first clinic signed, at €200 a month, and they asked us to sync with their booking system.",
     "cites": ["m1", "c1"]}
  ],
  "proof": ["c1"],
  "before_stage": [
    {"by": "ks", "question": "Is €200 a month the price after the pilot, or during it?"}
  ]
}
```

12. Run `companions memory demo-brief "<bank>" "<bank>/brief-plan.json"`.
    - **Accepted:** it prints the page's path, `<bank>/pages/brief-<occasion id>.md`. The engine writes the page's header and draft line itself; don't restate them.
    - **Rejected:** it exits non-zero, writes nothing, and prints one line per problem, such as `beat 2: the number 40 is not in any record it cites` or `beat 3 cites: m9 was retracted`. Fix only the named beats: cite the record that holds the number, or take the number out and ask the sprinter for it, one question. Never round, reword or spell out a number to get past the check. Then write the plan and run it again.
13. Once the page is written, retain one update to the occasion: `"uses"` set to the moment ids the script cites.

## Showing it
14. Read the page. Show the draft script lines in order, then a summary in 10 lines or fewer: the format, the estimated length from the page, the proof with its status, any conflicts to settle, and the before-stage questions. Give the page's path.
15. End with the offer to rehearse, as the turn's one question: "Want to rehearse? read it aloud and tell me which line felt wrong". When they say which line, rework only that line with them, in their words, and run the plan again.

Running `/brief` again after more sprint work rewrites the same page from the latest memory.
