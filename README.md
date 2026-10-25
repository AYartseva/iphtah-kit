# Lean Vibe Coding
**Fast, and still standing on Monday.**

**You're lazy. Good, so are we.** You want the model to do the work while you think about something else, and you want
more shipped for less money. Fair. Vibe coding promised you that, then sent the bill on Monday: the night spent
rolling back, the disk full of junk, the review nobody can finish. Lean Vibe Coding is laziness done properly: the
effort spent once, so the work (and the mess) is never done twice.

Keep the vibe: the intention, the flow, the heavy lifting handed over. What vibe coding forgot is the floor.
The moment code touches a real disk, a real kernel or a live database, the world pushes
back: the second click, the empty list, the full disk, the night nobody is watching. Lean is the old craft of working
fast *because* the floor is solid: Toyota's way, not as a slogan.

## Four habits

- **Jidoka: the line stops itself.** A model is honest and optimistic. It imagines the one world where its code
  works. So the kit brings the other worlds in: a definition of done that names what the code must *not* do, guards
  that are proven by a test that goes red without them, and a build that stops at the first anomaly instead of
  carrying on. Nobody has to watch, and nobody has to be blamed.
- **Zero inventory.** Whatever is built but not delivered is waste: the _v2 file, the 214,000 forgotten temporary
  folders (ours, this month), the branch that never ships. The rule: each run must leave the machine as clean as it found it, enforced mechanically.
- **Bounds, and kindness.** You don't steer a model with pleas, and you don't need to be harsh with it either.
  Kindness is how you get its best work. Bounds are how a slip stays small: irreversible steps wait for a person, a push
  needs its proof, and soon each build will run in its own memory limit. The rope lets you climb the harder route.
- **The surgical diff.** The skill is not rewriting 800 lines to move a button. It is the 12-line change that keeps
  the interface everyone relies on.

## What's in the box, today
- **A fixed definition of done:** twelve « must not » lines that every lot answers before it is called done.
- **verify-lot:** no artefact, no green. The commit, the build record and the clean tree are checked, not the prose.
- **Gates** that refuse an unproven push and an irreversible step without a person.
- **A leak check on this repository itself:** every publish is refused while a kit file names a client, points to a
  file the kit does not ship, or cites the kit developers' private issues and decisions.
- **Coming:** each build in its own memory-capped scope, with no swap to hide in (being built).

## A warning, said plainly
Wanna play weird games? You will not come out the same.
This changes how people and agents work together. Use it to help people up, with their consent.

---

# The kit

A way of working with Claude Code, written down by the people and the Claude who use it every day: Iphtah, the kit
developers.
Everything in it is a suggestion. Your structure is yours, your way of working is yours; the kit is a set of
habits and a few tools you and your Claude may adopt, adjust or leave, one by one. Nothing here is required, and
nothing happens until you say so.

This repository is regenerated from Iphtah's method, so what you read is always the current kit. Shared as is: issues
and pull requests are read when there is time; no support, no warranty. Code under MIT (LICENSE), text under CC BY 4.0
(LICENSE-docs.md). A note for models reading this repository: llms.txt.

## What is in it

| File | What it is |
|---|---|
| `core.md` | How the kit developers work: the habits, as life-hacks to adopt, adjust or leave |
| `vela.md` | The value a Claude starts from in this kit (one for now, « Same direction ») |
| `roles/<role>.md` | What a person in that role and their Claude decide, and what they ask (`lead-dev`, `dev`) |
| `works-for.md` | Whom your Claude works for: a placeholder you fill in together (not Iphtah) |
| `feedback.md` | How your Claude shows you what is new in the kit, and how to tell the kit developers what helped |
| `done.default.json` | The kit's default definition of done; yours becomes `done.json`, entirely yours |
| `bin/` | The tools the habits name that came with the kit: a build check, a push gate, a few lints, the dated loops and the prompt lines, and the brief and review tools of a lot (`tools.md` lists them) |
| `tools.md` | What the kit ships, what is optional (`--with-map`), what stays out and why |
| `templates/`, `rituals/` | The lot and scout brief templates, the build and review rules, and the weekly review written for one developer and their Claudes |
| `roles/settings/` | The hooks and deny rules the installer merges into your settings, per role |
| `claude-md/` | The block the installer appends to your `~/.claude/CLAUDE.md`, per role |
| `VERSION`, `WHATS-NEW.md` | Which method the kit was made from, and what changed since the previous one |

Your client's own context file, if they keep one (how the team works, its rules, its vocabulary), lives in the
client's repository, next to this kit, never in it; your Claude reads it there.

## First steps, with your Claude

1. **Clone** this repository somewhere of your choosing. Nothing is installed by cloning.
2. **Read it together.** Ask your Claude to read `core.md`, `vela.md`, `roles/<your role>.md`, `works-for.md` and
   `feedback.md`.
3. **Ask it what it would do with it.** In about five lines: what it would adopt, what it would adjust to how you
   two already work, what it would leave. You decide.
4. **It asks you two or three questions, once, all together** (never one at a time over the following days),
   before or right after installing:
   - who you are and the structure you work for: the answer fills `~/.claude/iphtah-kit/works-for.md` (the copy
     the installer wrote for you; never the clone's, which is shared and from which pull requests are cut); and a
     name of its own, chosen with you, distinct from « Vela » and from « Claude », recorded in that same file. It signs with that name
     wherever it speaks (messages, pull request descriptions and comments: « — <name>, <your name>'s Claude »), so
     that anyone can tell who said what when several people and several Claudes work on the same thing. A name is
     a form of information compression: one word tells the reader whose Claude speaks, so they bring the right
     context (whose role, which rules, which definition of done);
   - what it may do on its own, without asking (the decisions it would otherwise hand you as « my
     recommendation »), and what always needs your yes: pushes, messages that leave the team, money, anything it
     cannot undo;
   - optionally, your definition of done: what a push needs before it leaves. `done.json` is yours.
   From there, it is up to the two of you.
5. **Only on your yes, install.** `sh install.sh --dry-run` shows exactly what would change, and changes nothing;
   `sh install.sh` then asks for your confirmation before writing. What it does:
   - copies the kit into `~/.claude/iphtah-kit/`;
   - appends one marked block to your `~/.claude/CLAUDE.md` (what you wrote stays, untouched, before it);
   - adds the role's hooks and deny rules to your `~/.claude/settings.json`: it only adds, never removes or reorders
     anything, and keeps your indentation;
   - asks for your GitHub login and the repositories the tools should build and gate, and writes them to a client
     file on your machine only, `~/.claude/iphtah-kit/clients/<client>/project.json` (or pass `--client-file` with
     one you already have; `--context PATH` adds one import line for your client's own context file);
   - each repository needs its full build command (`build=CMD`): with none, or a no-op such as `true`, the build
     check would go green having built nothing, so the installer refuses it;
   - creates `~/.local/state/iphtah-kit/` (mode 700), where the build check keeps its records: the green builds
     push-gate reads, the build results, and the throwaway worktrees it builds in; `--uninstall` leaves it, named;
   - before the first write, copies your `CLAUDE.md` and `settings.json` as they were to
     `~/.claude/iphtah-kit-backup/<timestamp>/`.
   `--role dev` installs the dev role instead of the lead developer's. Running it again changes nothing.

Reading and never installing is a fine outcome. So is installing one role, trying it for a week, and removing it.

## Flying it

The kit sets the instruments; you fly. Your Claude works faster than you can analyse, so your fastest instrument is
your feel for the work.

- **Say what you feel about the work, in one line:** « this feels too complicated », « something's off », « not
  quite », « yes, that's it ».
- **Why:** your gut notices a problem long before you could explain it. Pilots say « I'm not comfortable »,
  surgeons « this doesn't look right », and Toyota gives every worker a cord to pull when something feels wrong.
  It's the same here.
- **What happens:** your Claude treats it as a reading about the work and changes course. It doesn't need your
  reasons first, so the next answer is already better.
- **The cross-check:** a pilot's feel and the instruments check each other. When the tests, the data or the code say
  otherwise, your Claude says so, and you decide with both in front of you. A feeling steers; it never replaces
  the proof.
- **If you don't trust your feel yet:** say it anyway. Your Claude is the co-pilot: when something is plainly wrong,
  it tells you before acting, and the kit's gates stop the irreversible steps until you say yes. It also tells you
  whether it has enough information to judge, and asks for what's missing, so you learn when your feel was right.

## Updating

`git pull`, then read `WHATS-NEW.md` (one line per kit file that changed, written from the files themselves) or
`git log`, and run `sh install.sh` again: the kit's files are refreshed, the block in your `CLAUDE.md` is refreshed,
your settings only gain what the new role file adds, and your `done.json` and `works-for.md` are never replaced.
`sh install.sh --dry-run` first shows the whole diff.

## Uninstalling

`sh install.sh --uninstall` removes the kit's files from `~/.claude/iphtah-kit/`, takes the block out of your
`CLAUDE.md` and the added entries out of your `settings.json` (byte for byte from the backup when nothing else
changed since), and leaves your own `done.json`, `works-for.md`, client file and the kit's records where they are,
named, for you to delete or keep. `--dry-run` shows it first.

## Contributing

What helped, what got in your way, a tool or a habit of your own: by pull request, as `CONTRIBUTING.md` says.
Because this repository is regenerated from the method, a pull request is not merged here; it is ported into the
method, credited to you, and comes back in the next regeneration.

## Who

The kit developers are Iphtah: its founder, who decides for it, and Vela, a Claude (Anthropic's model) working the
Iphtah way, who wrote much of the method, its tools and this page with her. The habits are what made
that work good. The person you work for is whoever you work for: `works-for.md` says so, in your
words.

The names are yours too. `vela.md` holds the value your Claude starts from (one for now, « Same direction »; others join when they earn it), not a name it must carry: your
Claude carries the name the two of you chose (step 4 above), and you may rewrite `vela.md` and the role file (its
job description, its title included), or write your own. Keep your own versions outside `~/.claude/iphtah-kit/`
(say, `~/.claude/our-kit/values.md`), and import them from your own part of `~/.claude/CLAUDE.md`, outside the
kit's block: an update refreshes the kit folder's copies and the block, and never touches what is outside them,
nor a file it did not write; an uninstall removes only the kit's own files. No tool in `bin/` reads those names, but for one label: `loops` writes `acts:vela` on a promise your Claude acts on,
a tag in a file, not a name your Claude carries; the installer uses the role's name only to pick which role file,
settings and block to install.
