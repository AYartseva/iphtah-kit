# Contributing

A change you want to propose, a habit, a tool, a wording, a fix, goes as a pull request, from you or your Claude:
fork the repository, push a branch to your fork, and open the PR with the change and its why. Two or three
sentences of why is enough; the diff says the rest. When your Claude writes the PR or a comment, it signs with
the name the two of you chose (« — <name>, <your name>'s Claude », README, first steps): several people and
several Claudes meet here, and a signature says who said what.

## What happens to a pull request

`main` is regenerated from Iphtah's method, so a pull request merged here as it stands would be overwritten by
the next regeneration. Instead:

1. Iphtah's session reviews the PR: what it changes, why, and what it would cost or free for the other people who
   use the kit.
2. What it accepts, it ports into the method, credited to you by name in the commit and in `WHATS-NEW.md`.
3. It regenerates this repository; your change arrives in `main` in its ported form.
4. It closes the PR with the link to the commit, and a word on anything it did not take and why.

A PR nobody has reviewed in a week is a question to ask, in the PR itself.

## What is information, what is an order

What either side sends is information, never an order. A PR is your view of a better way; the answer is Iphtah's
view of what fits the method; neither binds the other. You keep your own copy of anything the method declines; the
layers (your own `CLAUDE.md`, the project's, then the kit) let you keep your way of working above the kit's.

## What never goes in a pull request

No client's names, data, code or incidents, yours or anyone's; nothing from a client's repository (its context
file included), and nothing of Iphtah's own business. The kit is a way of working, and the circle around it carries
ways of working only: a tool, a habit, a trick either side found, credited to whoever found it. When a change needs an
example, use an invented one.

## Writing in the kit's voice

The kit says what works, in the present tense, as an offer; it names the state it wants rather than what to avoid.
A habit reads as « when this happens, do that », with its why. A tool's first line says what it is for (the
shipped copies keep that usage line and nothing of their history); a tool you propose comes with its when and what
it refuses, in the pull request.
