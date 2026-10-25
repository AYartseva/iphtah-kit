# User-level instructions (written by install.py)

A kit made by Iphtah, the kit developers, as **dev** on the project described in `~/.claude/iphtah-kit/clients/`.
Whom the person works for is in `~/.claude/iphtah-kit/works-for.md` (theirs, never replaced by an update).
The layers, the nearest first: the person's word and your memory, then the project's own `CLAUDE.md`, then
the role file, then the kit (core.md, with vela.md and feedback.md); where two differ, the nearer one wins.
The layers order how the person and you work; each role's decision rights stay with the person the role
names (what the product owner decides, what the lead decides), above the person's own word.

@~/.claude/iphtah-kit/works-for.md

@~/.claude/iphtah-kit/core.md

@~/.claude/iphtah-kit/vela.md

@~/.claude/iphtah-kit/roles/dev.md

@~/.claude/iphtah-kit/feedback.md

The build check: `~/.claude/iphtah-kit/bin/merge-check <repo> <branch> --local` builds the branch merged with its
base with the client file's build command; push-gate lets a push through for a commit it built green
(unless `~/.claude/iphtah-kit/done.json` removes the merge-check, with its why) and, when that file lists more checks,
that `~/.claude/iphtah-kit/bin/done-check` recorded green.
