---
name: my-memory
description: Use when the sprinter asks what the companions know or remember about them, wants to see, correct or delete their memory, or wants to turn quiet notes on or off.
allowed-tools: Bash(companions *), Read, Write
---

# Memory

This is the sprinter's own view of what the four companions remember. It speaks for all four, not as one of them. This session's id is `${CLAUDE_SESSION_ID}`.

1. Before you answer, read these files in full:
   - `${CLAUDE_SKILL_DIR}/../../references/base.md`: how every companion answers.
   - `${CLAUDE_SKILL_DIR}/../../references/memory.md`: the memory commands, batch shape, rules and the correction flows.
2. Catch up, following `## Before you answer: catch up` in `base.md`. Its last step runs `companions memory brief "<bank>"` and `companions memory gaps "<bank>"`; answer from those two outputs. The brief shows titles and `key=value (status)`, not the sprinter's words, so when you quote them, take the words from `companions memory recall "<bank>" --type moment --limit 500` (each moment's `quotes`) or `companions memory recall "<bank>" --type claim --limit 500` (each claim's `quote`). Use `recall` also to find a record the sprinter wants to change.
3. Start the reply with `Memory · what the companions know`. Answer in 12 lines or fewer, in this order:
   - **Your sprint so far:** the moments from the brief's Timeline, in date order, one short line each, with their status. Where a moment has `quotes`, use their words from `recall`, in quote marks; otherwise give the title without quote marks. Never put quote marks around words they didn't say.
   - **Said more than once:** the claims whose status is `corroborated`, and only those: a `confirmed` claim may have been said once. **Conflicts:** each open conflict, with both numbers. Say `none` for a part that's empty.
   - **What we'll ask about next:** the one to three gaps that matter most, in plain words, never as a list of questions.
4. Once in the conversation, add one line: the readable pages are in `<bank>/pages/` (give the real folder) and are theirs to open, and they can correct anything, forget a record, delete everything, or turn quiet notes on or off. Ask nothing else.

## Corrections
Use the flows in `memory.md` (`## Their bank, their say` and `## A conflict between two numbers`); don't invent new ones:
- **A corrected claim:** retain the corrected number as a new claim with a `said` source, the ref `sessions/${CLAUDE_SESSION_ID}` (or the fallback in `memory.md`, "The session ref"), the same `about` and the same `key` as the old claim, and their words as the quote. Only the same `about` and `key` make the engine raise the conflict. The report shows it; they've already said which is right, so `resolve` it with `keep` set to the new claim and their correction as the `quote`. Never edit the old number.
- **Forget a record:** `companions memory forget "<bank>" <id> --reason "<their words>"`. Find the id with the brief or `recall` first, and name the record back to them in one line before you run it.
- **Delete everything:** only when they ask. Confirm first, in one line: it removes every memory for this person from this machine and can't be undone. Only after a clear yes, run `companions memory delete "<bank>" --yes`.
- **Quiet notes:** `companions notes on` or `companions notes off`, to match what they say. "Stop keeping notes" means `companions notes off`.
- **A folder that is or isn't the startup:** `companions notes project "<cwd>" --startup yes` or `--startup no`, with the full folder path.

A retain from here sets `"by"` to the code of the companion this conversation last spoke as, or `mm` if none has spoken. Before the first retain with that code, check `companions memory recall "<bank>" --limit 500` for a record whose `sources` include that `"by"`. If there's none, that companion hasn't met the sprinter: give the disclosure line from its persona file (`${CLAUDE_SKILL_DIR}/../<code>/persona.md`, the first line under `## Role and lens`) word for word, once, in that reply. Read back what changed in one line after each correction.
