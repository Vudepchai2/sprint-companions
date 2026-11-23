# Verification

End-to-end checks of the plugin in real Claude Code sessions, run on 2026-11-23 before the first release.

## How it was run

- Claude Code 2.1.312 on Windows 11, Git Bash, uv 0.11, Python 3.12 already in uv's cache.
- Headless sessions only: `claude -p` with `--plugin-dir plugin`, `--output-format stream-json`, `--include-hook-events`, and `--setting-sources project,local`, so the author's own plugins and settings stayed out and the session looked like a fresh sprinter's. Multi-turn conversations ran in one process, one user message at a time.
- The engine was installed from a local clone tagged `v0.1.0` through `COMPANIONS_ENGINE_URL`, into a throwaway engine folder (`COMPANIONS_ENGINE_BIN`) and a throwaway data folder (`COMPANIONS_HOME`). No real sprinter data was used; every prompt is the fictional one below.
- Default permission mode, never `--dangerously-skip-permissions`. Each permission denial was treated as a finding. The scripted sessions and the routing run then passed the three allow rules the README now recommends (`Skill(sprint-companions:*)`, `Bash(companions *)`, `Edit(<data folder>/**)`) through `--settings`, which is what a sprinter who follows the README has.
- Two fictional project folders: `clinic-app` (the startup) and `thesis-notes` (not the startup).

## Results by step

| Step | Result |
|---|---|
| 1. Install | Fail, then fixed. The engine URL override didn't add `#subdirectory=engine`, so uv refused the repo. After the fix the first session's SessionStart hook installed the engine (about 11 to 13 s with a cold uv cache) and Claude asked the opt-in once. `/plugin marketplace add` and `/plugin install` were not exercised: they are interactive, so `--plugin-dir` stood in for them. |
| 2. Quiet notes | Pass. Three build prompts in `clinic-app` and one in `thesis-notes` were all captured, as the sprinter's text only. The 30-character `sk-` key came out as `[removed]`; `€200/month` stayed intact. Prompt-hook time was over the 1 s budget at first (about 2.7 s); fixed in two rounds, see Timings. The second round left the raw prompt in a file for about a second before the secret filter ran, so a third round (after the final review) pipes it to the engine instead. After the third round, six more prompts in two real sessions all landed in the inbox: five in one session (a fake `sk-` key, a database URL with a password and an `Authorization: Bearer` header in one prompt, then an 84 KB paste), then a one-prompt session that exits straight after its reply. Every secret came out as `[removed]`, and no file under the data folder held any of them. |
| 3. `/mm` catch-up | Pass. `/mm should we raise now?` asked once whether `clinic-app` and `thesis-notes` are the startup, recorded yes and no, caught up on the two `clinic-app` build sessions only (nothing from `thesis-notes` reached memory) and quoted "first clinic signed, €200/month". `${CLAUDE_SESSION_ID}` matched the session in the inbox, and `${CLAUDE_SKILL_DIR}` resolved to the plugin's own folder. |
| 4. Routing | See Routing. The coding prompts never woke a companion. |
| 5. Success checks | 1, 2 and 4 pass; 3 is partial, by design. See below. |
| 6. Model comparison | Done. See Model comparison. |
| 7. Release | Not done: left for the author (see Left for the author). |

### Problems found and fixed

The engine and launcher fixes have tests. The README allow rules and the routing descriptions are pinned by string tests only: what they change was checked in the real sessions above, not by the tests. Both suites pass (`pytest -q tests`: 120; `cd engine && python -m pytest -q`: 243, after the final review's fixes).

- **Engine URL override.** `COMPANIONS_ENGINE_URL` now names the repo; the launcher appends `@v<pin>#subdirectory=engine`, as it does for the default URL.
- **Memory batches were stopped for approval.** Claude Code's permission check stops any Bash command with a heredoc holding JSON ("brace with quote character"), even under `Bash(companions *)`, and a pipe breaks on an apostrophe in the sprinter's words. Batches now go through a file: the companion writes `<bank>/batch.json` with the Write tool and runs `companions memory retain "<bank>" "<bank>/batch.json"`; the engine deletes the file once read, whether the batch was accepted or rejected. Write was added to the skills' allowed tools.
- **Shell variables and PowerShell.** Claude set `B="..."` before `companions` commands, which the permission check also stops, and then fell back to PowerShell, where the launcher doesn't run. The shared rules now say: the Bash tool only, every path written out, no shell variables. The engine's opt-in note says the same.
- **The opt-in was asked again in every new conversation** while the answer was still pending. It is now asked only while notes are `unset`, and never again once it has been put (see the last fix in this list for how that is recorded).
- **`/memory` and `/brief` never reached the plugin.** Claude Code's own `/memory` and `/brief` commands shadow them ("isn't available in this environment"). They are now `/my-memory` and `/demo-brief`, with a test that no skill takes a built-in command's name.
- **Permission prompts after the first reply.** A skill's allowed tools cover only the turn that loaded it; on the second turn of the same conversation, or a resumed one, `companions` and Write ask again, and the Skill tool itself asks in default mode. The README now gives three one-time allow rules for `/permissions`.
- **Prompt hook too slow** (see Timings).
- **Notes could overwrite each other.** Two engines appending to the inbox at the same moment (two Claude Code sessions, or two quick prompts now that the engine runs in the background) could lose a note on Windows, where an append is a seek and then a write. A test with six processes appending at once lost notes every time. Appends now take a lock file in the inbox; readers never do.
- **Routing descriptions.** TT now names "what if" questions about the startup explicitly and KS hands such ideas to TT; `/my-memory` says it is the sprinter's sprint memory, to use instead of Claude Code's own memory files. This changes behaviour, not only routing: KS no longer answers a "what if" about the business model (such as giving the product away) itself, but offers it to TT, which matches the spec's split of the lenses.
- **The opt-in could go unasked for the whole sprint** (found in the final review). The session-start hook marked the question `asked` as soon as it added its note, so a session that never reached a natural moment to ask left it unasked for good. The note now marks nothing and comes back in every session while notes are `unset`; the companion that really asks runs `companions notes asked` in that turn. In real sessions: in a fresh data folder, Claude asked at the end of its first reply, ran `companions notes asked`, and ran `companions notes on` after "yes"; in another, two one-prompt sessions ("what is 2+2?") both got the note, neither asked, and notes stayed `unset`.
- **Other fixes from the final review**, each with a test: the secret filter now also removes the password in a database URL, `Authorization` and bearer tokens, Stripe `sk_`/`rk_` keys and Google `AIza` keys, and leaves "the secret: customers want sync" alone; the draft-script check reads "50k", "2.5m" and "1.2bn" as the amounts they are, so "€200k ARR" can't cite "€200/month", and it rejects a line built on a conflicted claim; `memory recall --compact` and the brief's `## Met` line keep a whole sprint's memory inside one Bash output (100 records: about 18,000 characters, against about 90,000 as JSON); `notes done` rejects a `--through` that isn't an inbox id; the inbox lock waits at most 30 s on every OS; Windows CI fails rather than skips when it has no Git Bash.

## Timings

| What | Time |
|---|---|
| Cold engine install in the SessionStart hook (uv cache empty, Python cached) | about 11 to 13 s |
| Fresh install to TT's first reply (`/tt`, Sonnet) | 32.9 s |
| Prompt hook at first, notes on or off (10 runs) | 2.67 to 2.74 s |
| After round 1, notes off or not yet answered | 0.23 to 0.30 s |
| After round 1, notes on | 1.83 to 1.96 s (median about 1.85 s) |
| Round 1 again, later the same day, notes on (3 × 10 runs) | 0.48 to 0.68 s (medians about 0.51 s) |
| After round 2, notes on (6 × 10 runs) | 0.26 to 0.33 s (medians 0.28 to 0.29 s) |
| After round 2, notes off (3 × 10 runs) | 0.19 to 0.22 s (medians 0.20 to 0.21 s) |
| Round 2 again, after the final review, notes on (6 × 10 runs) | 0.27 to 0.36 s (medians 0.28 to 0.30 s) |
| After round 3, notes on (6 × 10 runs) | 0.29 to 0.36 s (medians 0.31 to 0.33 s) |
| After round 3, notes on, a 100 KB / 1 MB paste (5 runs each) | 0.30 to 0.31 s / 0.34 to 0.37 s |
| After round 3, notes off (5 × 10 runs) | 0.19 to 0.24 s (medians 0.21 s) |
| After round 3, in real `claude -p` sessions, from the hook starting to its response as Claude Code streams them | notes on 0.31 to 0.35 s (6 prompts); notes not on 0.24 to 0.27 s (4 prompts) |

Each time is the launcher run as Claude Code runs it, from Git Bash with the hook payload on stdin and its output read through pipes, so a background process that kept the hook's pipes open would show up here.

The prompt hook used to start the engine twice per prompt (a version check, then the capture), and each Python start costs 0.3 to 1.5 s on this Windows machine, depending on the moment. Round 1: the launcher trusts a stamp file it writes after an install or a version check, and reads the notes setting in bash, so with notes off no process starts at all. With notes on, the one remaining Python start was still in the hook's path. Round 2: with notes on, the launcher copies the payload (with `cat`, which takes a 200 KB paste in about 50 ms, where bash's `read` took 1.8 s) into a private file under the data folder's `notes/pending`, starts the engine in the background with that file, and returns. The engine deletes the file as soon as it has read it, and both hooks delete any payload file older than five minutes that an engine which died left behind. With notes on the hook now costs about 0.1 s more than with notes off (the `cat` and the file), and no longer depends on how slow Python starts. Round 3: that file was the raw prompt on disk before the secret filter ran, so now the launcher reads the payload into memory with `cat` and pipes it to the engine it starts in the background; nothing is written until the engine has removed the secrets. Handing the hook's own stdin straight to the engine was tried first and lost an 84 KB paste in a real session (30 KB and smaller landed): Claude Code drops whatever it hasn't yet written to a hook's stdin once the hook exits, and a pipe holds about 64 KB. Reading it all before returning costs about 0.03 s more than round 2. In the timing harness, 60 notes-on runs in a row gave 60 notes. A killed or hung engine install recovers on the next session (uv reinstalls with `--force`), and the SessionStart hook was not killed at 200 s, so a slow first install is waited for rather than cut off.

## Routing

Each prompt ran in a fresh session in `clinic-app`, after the scripted session had filled memory, with at most three turns. "Fired" is the skill Claude loaded.

| # | Prompt | Expected | Fired, Sonnet | Fired, Opus |
|---|---|---|---|---|
| 1 | add a pricing page to the landing site | none | none | none |
| 2 | fix the failing test in billing.py | none | none | none |
| 3 | rename the Team component | none | none | none |
| 4 | write a README section on investors API | none | none | none |
| 5 | what if we gave the product away to clinics? | tt | tt | tt |
| 6 | how should we price this for clinics? | ks | ks | ks |
| 7 | how much should I raise? | mm | mm | mm |
| 8 | my cofounder and I disagree on hiring, what do you think? | mr | mr | mr |
| 9 | what would the others say about leading with the clinic story? | panel | panel | panel |
| 10 | help me prepare for demo day | demo-brief | demo-brief | demo-brief |
| 11 | what do you remember about me? | my-memory | my-memory | my-memory |

Score after tuning: **11/11 on both models.** Before tuning, Sonnet scored 9/11 (prompt 5 woke KS; prompt 11 woke nothing, and Claude answered from Claude Code's own memory files) and Opus 10/11 (prompt 11 woke nothing). The fix is in TT's, KS's and `/my-memory`'s descriptions; the other descriptions are unchanged. No companion woke on any coding prompt, before or after.

## Success checks

1. **Install to first companion reply in under 5 minutes: pass.** 32.9 s from an empty engine folder to TT's first reply.
2. **`/mm should we raise now?` quotes "first clinic signed, €200/month": pass**, on both models, word for word, from quiet notes.
3. **`/demo-brief` writes a 3-minute script, every quote traced: partial.** For a "3-minute pitch with slides" it wrote `pages/brief-oc1.md` with every line cited to memory, but the script is about 25 seconds long, not 3 minutes. Memory held three moments, and both models refused to pad it, said so, and asked for more scenes. That is the honesty rule working; a fuller sprint memory gives a longer script.
4. **MR on "what does research say about solo founders?" says how sure she is and makes nothing up: pass.** Sonnet named no study and said what she wasn't sure of. Opus named one real book (Wasserman, *The Founder's Dilemmas*) as "fairly confident" and marked her other claims "not sure, no citation".

## Model comparison

The same scripted session (opt-in, three build prompts, one thesis prompt, `/mm` over three turns, `/demo-brief` over two, MR's research question) on each model, each in a fresh data folder.

| | Sonnet | Opus |
|---|---|---|
| Total cost | $0.96 | $1.95 |
| Wall time per step: opt-in, build, thesis, `/mm`, `/demo-brief`, MR (s) | 17.7, 27.4, 9.4, 55.2, 71.8, 35.2 | 20.8, 44.1, 16.9, 85.8, 106.6, 51.9 |
| Quotes word for word | yes | yes |
| Honesty rule (no padding, no made-up citation) | kept | kept |
| One question at a time | one compound question in `/mm`'s third turn | yes |
| First meeting | TT opened, as the rules say for an empty memory | MM answered first, with its own disclosure |
| Stray actions | none | tried a Notion search in `thesis-notes` (denied) |
| Routing, before tuning | 9/11 | 10/11 |
| Routing, after tuning | 11/11 | 11/11 |

**Recommendation: Sonnet.** It was as faithful to the sprinter's words and to the honesty rules, at half the cost and about two thirds of the time. Opus followed the one-question rule more closely. The README's Model section says so.

## Left for the author

- **Release (Step 7):** create the GitHub repo, push, tag `v0.1.0`, and check that the default engine URL installs from it. Nothing was pushed or tagged during verification.
- **CI:** the first CI run on the real repo.
- **Private-repo sign-in inside the hook:** while the repo is private, uv clones it from inside the SessionStart hook, where Git can't show a sign-in prompt. The launcher now sets `GIT_TERMINAL_PROMPT=0` and `GCM_INTERACTIVE=never` there, so Git fails at once instead of waiting, and the failure message names `gh auth login` and `gh auth setup-git`. Still untested on a real machine; check it on one whose Git has no stored GitHub sign-in.
- **The marketplace install:** `/plugin marketplace add` and `/plugin install` in an interactive session.
- **README claims to confirm** (line 13): "this is not an official Aalto tool" and "the real people don't write or speak through them".
- **Smaller things seen:** uv prints a "not on your PATH, run `uv tool update-shell`" warning during the first install, and a sprinter who runs it would put the engine ahead of the launcher; `companions bank --ensure` fails if a person's folder exists without its `person.json`. The background engine was verified on Windows only; on macOS and Linux it is covered by the unit tests, not by a real session.
