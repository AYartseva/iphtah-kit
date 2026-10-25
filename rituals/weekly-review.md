# The weekly review, for one developer and their Claudes

A short ritual, once a week, at a time the developer picks (Friday morning works: the week is fresh and the next one
has not started). Twenty minutes. Its job is to turn what happened this week into a gesture, a tool or a closed
promise, so the next week starts lighter than this one. Nothing here is required: adopt it, adjust it, leave it.

**Who does what.** The developer decides. Their Claude prepares (it reads, it counts, it proposes) and writes down what
the developer decides, the same day. A script detects, Claude interprets, the person decides.

## 0. Celebrate first (two minutes)

Read the week's wins before any defect: what shipped, what a review caught early, what a colleague did well. Say the
best three aloud, with who did them. Then one question: **what made it work, and can it become a tool or a line in a
template?** A success that repeats is worth a tool, the same way a lesson is. If you keep a `good-news.md` in your
state folder, the Claude reads it and appends to it.

## 1. The promises (five minutes)

`~/.claude/iphtah-kit/bin/loops list` shows every open promise; `loops list --all` the closed ones.

- A promise that is past its date: do it now, re-date it (`loops close K --dropped "why"` and add it again), or drop it
  with its reason. A date nobody keeps is a lie the next session believes.
- A promise with no date: `loops add "YYYY-MM-DD HH:MM" "who" "what" --acts vela|owner|other:<slug>`. The stop hook
  already refuses to let a turn end on an undated « I'll »; this is the sweep for the ones that slipped.
- A promise that waits on someone else: say who, and when you will ask again.

## 2. The lots (five minutes)

`~/.claude/iphtah-kit/bin/lots --client <c> report` (once you launch lots with `launch-lot`, the ledger is your own, in
`~/.claude/iphtah-kit/clients/<c>/lots.json`) shows predicted against actual per lot.

- A lot that took clearly longer than its class predicted: what was missing from its brief (the purpose, a stop
  point, a related issue)? Write it as a line in your own brief template, not as a story.
- A lot that came back red twice: the context was missing, not the effort. What would have made it green the first time?
- Reviews: what did the fresh-eyes review find that the builder's tests did not? Which kind of defect came back this week
  despite a rule in `rituals/brief-and-review-rules.md`? A kind that comes back becomes a check (a lint, a test), not a
  longer rule. Which question is missing from the review brief? Add it.

## 3. The setup itself (five minutes)

- Ask the Claude of a fresh session: « does the context you loaded make sense for what you are here to do? » Fix what it
  says is contradictory, stale or missing (`works-for.md`, your role file, `done.json`).
- Read `WHATS-NEW.md` if the kit changed: for each line, useful to you, in your way, or neither? Mark it `Answered` with
  your verdict so the next update keeps only what is open.
- Is a guard you added this week proven? A guard has a test that fails without it: cut the guard, see the test go red.

## 4. Decide, write, close (three minutes)

For each point above that needs a change, one of: a loop with a date, an issue with an owner, a line in a template or in
`done.json`, or « accepted because… » written where the next session will read it. Nothing to decide is a fine answer:
say it and stop. The Claude writes the decisions down before the review ends, in `<state>/weekly-review/YYYY-MM-DD.md`:
what is true now, what is in flight and who waits for whom, and the next step. A reader who starts tomorrow without any
memory of this meeting should be able to carry on from that page alone.
