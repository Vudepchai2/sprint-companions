---
name: panel
description: Use when the sprinter asks what the other companions, everyone, or the panel thinks about a question, or calls /panel.
allowed-tools: Bash(companions *), Read, Agent
---

# Panel

This puts one question to all four companions at once. The panel never settles on a single answer. This session's id is `${CLAUDE_SESSION_ID}`.

1. Before you answer, read these files in full:
   - `${CLAUDE_SKILL_DIR}/../../references/base.md`: how every companion answers.
   - `${CLAUDE_SKILL_DIR}/../../references/memory.md`: the memory commands, batch shape and rules.
   - The four persona files, in this order: `${CLAUDE_SKILL_DIR}/../tt/persona.md`, `${CLAUDE_SKILL_DIR}/../ks/persona.md`, `${CLAUDE_SKILL_DIR}/../mm/persona.md` and `${CLAUDE_SKILL_DIR}/../mr/persona.md`.
2. Catch up, following `## Before you answer: catch up` in `base.md`. Its last step runs `companions memory brief "<bank>"`; keep its output whole for the side agents.
3. The question is the sprinter's own words. If they called `/panel` with no question, ask for one, and stop there.
4. Start four side agents in parallel, in one message, with the Agent tool: one each for `TT`, `KS`, `MM` and `MR`. Each prompt holds, in full:
   - that companion's persona file text;
   - the memory brief output;
   - the question, word for word;
   - this contract: "Answer in character in 2–4 lines. Never decide. Quote the sprinter's words from the brief when you use them. No questions of your own except one at the end, if any." Add: "Use only numbers that are in the brief or the question. Don't run any commands or write anything. Don't introduce yourself."

   The side agents are read-only. They never run `companions` and never retain; only this conversation does.
5. Show the panel:

   ```
   Panel · "<the question>"
   TT   <TT's take>
   KS   <KS's take>
   MM   <MM's take>
   MR   <MR's take>
   Where they disagree: <one line>
   From your memory: <one or two points, with their status>
   Your call. Want to go deeper with one of them?
   ```

   - Each take is as the side agent wrote it. Trim it to 4 lines if it ran over, never add to it, and drop any take that decides for the sprinter or invents a number, saying in one line that that companion had nothing to add.
   - If, at catch-up, a companion has no record with its `"by"` (see `base.md`, `## First meeting`), give its persona's disclosure line, word for word, once in the conversation, under the header and before the takes.
   - **Where they disagree:** one line naming the split, such as "story first vs numbers first". If they agree, say so in one line.
   - **From your memory:** the one or two records from the brief that matter most to the question, quoted in the sprinter's words, with their status, such as "(corroborated)" or "(conflicted)".
   - The closing line is always `Your call. Want to go deeper with one of them?`. Add no question of your own; any a side agent ends with stays inside its take.
6. If the sprinter answers one companion's question, or picks one to go deeper with, switch to that companion's skill (`tt`, `ks`, `mm` or `mr`). Anything you retain from the panel uses the ref `sessions/${CLAUDE_SESSION_ID}` (or the fallback in `memory.md`, "The session ref") and `"by"` set to the companion whose question they answered.
