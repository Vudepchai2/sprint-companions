# Sprint companions

Sprint companions is a Claude Code plugin for Aalto Founder Sprint sprinters, built for one job: your demo-day story. If you opt in, it quietly keeps what you type while you build, and when you ask, four AI companions spar with you on turning the sprint into a story, in your own words.

The companions never decide for you, never score you, ask one question at a time, and quote you word for word. Your memory and notes stay on your machine.

**See it first:** [`docs/demo.html`](docs/demo.html) walks through five moments from a fictional sprinter's week. Download it and open it in a browser; GitHub shows only its source.

[Quiet notes](#quiet-notes) · [After a customer call](#after-a-customer-call) · [/demo-brief](#demo-brief-draft-script) · [/panel](#panel) · [/my-memory](#my-memory) · [Install](#install) · [Privacy](#privacy) · [Limits](#limits) · [Model](#model)

## The companions

Each companion is inspired by a member of the Aalto Founder Sprint team and goes by their initials. They are AI companions written in a style drawn from public talks, interviews and writing, plus the author's own notes. They are not the real people, the real people don't write or speak through them, and this is not an official Aalto tool.

<table>
<tr>
<td width="50%" valign="top">
<img src="art/tt.svg" width="64" height="64" alt="TT (placeholder image)">

**TT** · inspired by Tai Tran<br>
*Ideas, brainstorming, "what if", and your very first session.*

Energetic and opinionated. Goes for the crazy version, cuts it down to one thing you can test this week, and says out loud when a call might be wrong.

**Leave with an idea you'll try this week.**

> I'm TT, an AI companion inspired by Tai Tran. I'm not him, and I don't speak for him.
</td>
<td width="50%" valign="top">
<img src="art/ks.svg" width="64" height="64" alt="KS (placeholder image)">

**KS** · inspired by Kasper Suomalainen<br>
*Product, business model, pricing, unit economics, money.*

Calm and grounded. Asks who pays, how much and how often, then where the number on your slide comes from.

**Know who pays you, and why.**

> I'm KS, an AI companion inspired by Kasper Suomalainen. I'm not him, and I don't speak for him.
</td>
</tr>
<tr>
<td width="50%" valign="top">
<img src="art/mm.svg" width="64" height="64" alt="MM (placeholder image)">

**MM** · inspired by Mårten Mickos<br>
*Fundraising, investors, the pitch, ambition, the honest check.*

Approachable at first, more direct as he gets to know you. Turns "how much should we raise?" into "why raise at all?", then asks for the proof, then asks you to think bigger.

**Walk into demo day knowing why you're raising.**

> I'm MM, an AI companion inspired by Mårten Mickos. I'm not him, and I don't speak for him.

<!-- TODO(author): link the existing AI Marten here, under MM, only once its maker has confirmed he's happy with that. No link until then. -->
</td>
<td width="50%" valign="top">
<img src="art/mr.svg" width="64" height="64" alt="MR (placeholder image)">

**MR** · inspired by Maija Renko<br>
*Team, cofounders, hiring, people, what the research says.*

Warm and research-minded. Asks who on the team owns what, and what customers did rather than said. Says how sure she is, and never makes up a citation.

**Know what your team and your evidence are telling you.**

> I'm MR, an AI companion inspired by Maija Renko. I'm not her, and I don't speak for her.
</td>
</tr>
</table>

The images are placeholders until the original art arrives (see [`art/`](art/README.md)).

### How they talk with you

- **The right one answers first.** Ask a question and the companion whose lens fits picks it up, under a header such as `MM · fundraising`. Call one by name (`/tt`, `/ks`, `/mm`, `/mr`), or say "ask MR instead" or "what would KS say?" at any time.
- **Only when you ask.** A coding request never pulls a companion in. "Add a pricing page" is a coding task; "how should we price this?" is for KS.
- **Each says who it is** the first time you meet, with the line on its card.
- **One question per turn.** A companion asks the question behind your question, and when your memory already holds the answer, it uses it instead of asking:

```
> /mm should we raise now?

MM · fundraising
(caught up on your last 4 build sessions)
On Tuesday you wrote "first clinic signed, €200/month".
One paying customer changes this conversation. Why raise
before the second?
```

- **Your words, not theirs.** When a companion reflects something back, it quotes you exactly. Every number it uses is one you gave it.
- **Suggestions, never verdicts.** No scores, ratings or grades, of you, the idea or the pitch. You decide; your customers decide.

## Quiet notes

Most of your sprint happens while you're building, not while you're talking about the story. Quiet notes catch that, if you want them to.

- **Asked once.** At a natural moment in a session, Claude asks, in one line (if your first session gives it no moment to ask, a later one does):

  > Want the companions to keep up with your build sessions? They only keep what you type, on this machine. You can turn it off any time.

  Nothing is kept until you say yes. Once it has been asked, it isn't asked again: say "keep notes" to turn them on later, "stop keeping notes" to turn them off, or use `/my-memory`.
- **Only what you type.** A small hook adds each prompt you type to a local inbox on this machine, with the time and the project folder. It never keeps Claude's replies, tool output or code Claude writes. Anything you type or paste into a prompt is kept on this machine as you typed it, pasted code or error messages included, with anything that looks like a key, token or password removed before it's written. No AI runs while you build. The hook is silent, and it never blocks or fails your prompt.
- **Only your startup.** The first time the notes hold a folder the companions haven't seen, they ask once which folders are the startup:

  > Is `clinic-app` your startup? And `thesis-notes`?

  Notes from folders you say aren't the startup are never read.
- **Caught up when you ask.** The next time you call a companion, `/my-memory` or `/demo-brief`, it reads the inbox and keeps only the story material, in your words: customers, numbers, decisions, turning points, what shipped and when. "Fix the CSS" is dropped. It says so in one line, such as `(caught up on your last 4 build sessions)`. The first call after a long stretch is a little slower.
- **Cleared after 30 days.** Whatever is left in the inbox is deleted after 30 days.

To be honest about what this catches: most prompts are coding instructions, so the notes mostly yield what you shipped and when ("we shipped invoicing in 9 days"), plus the odd decision. The best material happens elsewhere.

## After a customer call

Customer calls happen outside Claude Code, so quiet notes can't hear them. That's where the best story material comes from, so the one habit worth building is this: after a customer call, tell a companion what happened, in a line or two.

```
/tt just talked to a clinic, they'd pay €200/month if it syncs with their booking system
```

The companion keeps it in your words, and it's there for the next question, the panel and your demo-day script. If you'd rather talk than type, use your computer's own dictation (Win+H on Windows, Fn twice on a Mac).

## /demo-brief (draft script)

`/demo-brief` turns your memory into a demo-day brief you can practise from.

1. It asks for what's missing, one question per turn: the date, the format and length ("3-minute pitch with slides, no Q&A"), and who'll be in the room and what they care about, in your words.
2. It writes a one-page brief to your memory's `pages/` folder, headed:

   > Draft: in your words, from your memory. Change anything that doesn't sound like you.

   - **A draft script**, sized to your format at about 150 spoken words a minute, with the estimated length shown. Each line cites the moment or claim it comes from, with your original words under it. Every number in a line has to appear in the record it cites: the engine rejects the brief otherwise, so the script can't invent or round a number.
   - **Proof points**, confirmed ones first, then corroborated, each with its status. Conflicting numbers are flagged, never hidden.
   - **Before you go on stage**: the open questions, and the one question each relevant companion would still push on.
3. It summarises the brief in the chat and offers to rehearse: read it aloud, say which line felt wrong, and you rework that line together, in your words.

Run it again after more sprint work and it rewrites the same page from your latest memory.

## /panel

`/panel` puts one question to all four companions at once and shows their takes side by side, two to four lines each, in character:

```
Panel · "should we lead the demo with the clinic story?"
TT   Lead with it. Then cut everything that isn't it. ...
KS   Only if "€200/month" is on screen. ...
MM   ...
MR   ...
Where they disagree: story first vs numbers first
From your memory: "we lost two clinics to a cheaper tool" (corroborated)
Your call. Want to go deeper with one of them?
```

The panel shows where they disagree and the one or two things from your memory that matter most. It never settles on one answer. A panel question costs about four times a normal one, because each companion answers separately.

## /my-memory

All four companions share one memory of you. `/my-memory` shows it in the chat, in 12 lines or fewer:

- **Your sprint so far:** the moments, in date order.
- **Said more than once,** and **conflicts.**
- **What the companions will ask about next.**

Every point shows where it came from (something you said, or a quiet note from a given day and project) and its status:

| Status | Meaning |
|---|---|
| `said` | You said it once. |
| `corroborated` | The same number came up in two different sessions. |
| `conflicted` | Two different numbers for the same thing. A companion asks you once how they fit, and never picks one for you. |
| `confirmed` | You settled it. |

The memory is yours. It's also written out as readable pages you can open in any editor. Through `/my-memory` you can correct anything, forget a record, delete everything, or turn quiet notes on or off.

## Install

You need three things:

- **[Claude Code](https://claude.com/claude-code).**
- **Git.** On Windows, install **Git for Windows** (`winget install --id Git.Git -e`, or from git-scm.com) and restart Claude Code. Without it, Claude Code has no Bash tool and the companions can't run. On a Mac, accept the command line tools prompt if it appears.
- **uv**, a small installer for Python tools. If it's missing, the first companion call stops and shows you the one command for your computer. It needs no admin rights:
  - Windows (PowerShell): `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`
  - macOS and Linux: `curl -LsSf https://astral.sh/uv/install.sh | sh`

**While the repository is private.** During the private beta, accept the GitHub invitation you received first. Git then has to sign in to GitHub with that account, because both the plugin and its engine are fetched from this private repository. The surest way, on any computer, is GitHub's command line tool (`winget install --id GitHub.cli` on Windows, `brew install gh` on a Mac, or see cli.github.com). Then run, in a terminal:

```
gh auth login
gh auth setup-git
```

Do this yourself in a terminal. Never paste passwords or tokens into Claude.

**Then, in Claude Code,** type these two lines, one at a time:

```
/plugin marketplace add Vudepchai2/sprint-companions
/plugin install sprint-companions@sprint-companions
```

Choose to install it for you (user scope). If Claude Code says to reload plugins, type `/reload-plugins`, or start a new session.

**Fewer permission prompts (recommended).** Claude Code asks before a companion runs its `companions` commands after its first reply, and before it saves to your memory folder. To say yes once for good, type `/permissions`, choose **Allow**, and add these three rules:

```
Skill(sprint-companions:*)
Bash(companions *)
Edit(~/SprintCompanions/**)
```

The first lets Claude call a companion when you ask for one, the second runs the companions engine, and the third lets the companions write to your memory folder and nowhere else. (If you set `COMPANIONS_HOME`, use that folder in the third rule.) The second also covers `companions memory delete`, which removes your whole memory, but the companions always ask you in the chat before deleting it, and delete only after a clear yes.

**First run.** The first time it starts (in a new session, or at the first companion call), it installs the companions engine at the exact version this plugin pins, into a private folder (`~/.sprint-companions/engine-bin`), with a Python to run it. It happens once per engine version (an update that changes the pin installs the new one) and can take a few minutes. Then try `/tt`, or just ask "what's the boldest thing we could show on demo day?"

**Updates.** Type `/plugin`, open the **Marketplaces** tab, choose `sprint-companions` and **Update marketplace**, then open the plugin under **Installed** and choose **Update now**. The next companion call installs the matching engine by itself. Your memory isn't touched.

## Privacy

- **Everything stays on your machine.** Your memory and the quiet-notes inbox live in `~/SprintCompanions` (on Windows, `%USERPROFILE%\SprintCompanions`). Set `COMPANIONS_HOME` to put them somewhere else.
- **Nothing is uploaded, and there are no usage stats.** The engine makes no network calls. The only downloads are the engine itself and a Python to run it, through uv, at first run and when an update changes the engine version.
- **Claude still sees the conversation.** What you type, and the parts of your memory a companion reads to answer you, go to Claude like anything else in a Claude Code conversation.
- **Quiet notes keep only your prompts**, and only after you opt in. They never keep Claude's replies, tool output or code Claude writes. Anything you type or paste into a prompt is kept in the inbox on this machine, from every folder you work in, with secrets removed before it's written. But only notes from folders you've confirmed as the startup are ever read into your memory, and only the story material from them. Anything left in the inbox is deleted after 30 days.
- **The demo-day audience** is kept only the way you describe it ("seed investors and corporates, they care about paying customers"). The companions keep no records about named people in the audience and research nobody.
- **It's yours.** The readable pages in your memory folder are yours to open. Correct, forget, delete everything, or turn quiet notes off, any time, through `/my-memory`.

## Limits

- **Cofounders on separate laptops have separate memories.** Nothing is shared across a team. Each of you builds your own memory, from your own typing.
- **No voice.** There's no voice conversation and no recording. Type, or use your computer's dictation.
- **No scores.** The companions don't measure your pitch or your delivery, and don't rate you, your idea or your team.
- **No research on people.** The companions don't look up your audience, investors or market. Claude can already help with that in an ordinary conversation.
- **Quiet notes mostly see coding instructions.** The story material from them is thin unless you tell a companion after a customer call.
- **Inspired by, not the real thing.** Each companion's style comes from public material and the author's notes, built in about three days. "Recognisable" was the bar, not "identical". They can be wrong, and they never speak for the people who inspired them.
- **Claude Code only**, on Windows, macOS or Linux. There's no app of its own. On Windows it needs Git for Windows.
- **A panel costs more.** One `/panel` question costs about four ordinary ones.

## Model

The companions run on whatever model your Claude Code uses. We recommend Sonnet. The engine does the exact work (keeping your words, counting sources, flagging conflicts, and checking every number in the draft script), and the model's job is to listen and ask one good question. On the same scripted session, Sonnet and Opus both quoted the sprinter word for word, refused to pad a thin draft script and made up no research; Sonnet cost about half as much and answered faster. Opus kept to one question at a time a little more closely. The details are in [`docs/verification.md`](docs/verification.md).

## How it's built

- `plugin/`: the Claude Code plugin. The four companion skills (`skills/tt`, `ks`, `mm`, `mr`), each with a `persona.md` that holds its disclosure, outcome line, voice and sources; the `demo-brief`, `panel` and `my-memory` skills; the shared rules in `references/`; the hooks for quiet notes; and the launcher, `bin/companions`.
- `engine/`: the `companions` command, Python standard library only. It owns the memory bank, the quiet-notes inbox, the secret filter and the draft-script check.
- `research/`: the public sources behind each persona.

Run the tests with `cd engine && python -m pytest -q`, then `pytest -q tests` from the repo root.

## Licence

Apache-2.0. See [`LICENSE`](LICENSE) and [`NOTICE`](NOTICE).
