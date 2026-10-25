# What the kit ships, what is optional, what stays out

Written for you and your Claude to read before installing. Everything is a suggestion; every tool runs in a home with no
Iphtah folder and writes only under `~/.claude/iphtah-kit/` and `~/.local/state/iphtah-kit/`.

## In (installed with the kit)

| Tool | What it is for | On your machine |
|---|---|---|
| `loops` | Dated promises (« I'll do X for Y by Z »), one file per client: `loops add`, `list`, `close`, and `stop-check`, the Stop hook that keeps a turn from ending on an undated « I'll » | The file is `<state_dir>/open-loops.md` of your client file |
| `prompt-lines` | A few lines in front of each prompt and at session start: the time, your open and overdue loops | Hooks added to your settings; it shows nothing it cannot read |
| `launch-lot` | One gesture at a lot's launch: ledger entry, related open issues, a brief skeleton | Fills `templates/lot-brief.txt`; the ledger is yours (`lots`, in `clients/<c>/lots.json`) |
| `lots` | The lot ledger: predicted against actual, per lot | Local to you; the pooled and registry views skip what they cannot read |
| `open-issues` | Every open issue of your repositories, one line each, for the brief | Needs `gh` signed in |
| `review-brief`, `fix-brief` | The fresh-eyes review brief and the fix brief, cut to the severity the diff touches | Fill the rules of `rituals/brief-and-review-rules.md` |
| `verify-lot` | Checks the artefact an agent reports (commit, green record, clean tree) before you trust its prose | Reads your client file |
| `ship-lot` | The smallest version of the push gesture: `verify-lot` must say OK for the commit and the PR's base, each `--marker` must be absent from the live base and present in HEAD, then it pushes, opens the PR with `gh pr create --body-file`, and records the lot done in your ledger (`lots done`) | Only with `--approved`; it prints its plan and stops without it. No ticket registration, no map write, no message to anyone |
| `shelf` | The work that is built but not delivered: local branches ahead of their base that the remote does not have | Reads your client file |
| `mutant-check` | Proves a guard: it cuts the lines a branch added and shows which test goes red | Python, and TypeScript or Java where the tool for them is installed |
| `heavy-gate` | Two hook gates. It refuses a `gh` command (issue or PR comment, create, edit, review) whose double-quoted text holds a backtick or a `$`, which bash would rewrite before it leaves (it names the file route); and `pkill`/`pgrep` with `-f`, which also match your own command | Its full-suite gate and its slot queue stay off (they need a remote build machine) |
| `merge-check`, `done-check`, `push-gate`, `when-quiet` | The build check and the gate before a push | As before |

`rituals/brief-and-review-rules.md` (the build and review rules), `templates/` (the lot and scout briefs) and
`rituals/weekly-review.md` (the weekly review, written for one developer and their Claudes) come with them. The scout
brief (`templates/scout-brief.txt`) is there too: your Claude fills it by hand, since `scout-row` stays out (below).

## Notes

- Dates and times in `loops` and the prompt lines are in the zone `IPHTAH_TZ` names (an IANA name such as
  `America/New_York`), Paris time when it is unset. Set it once, before the first loop: the loop lines hold no zone.
- `acts:vela` in a loop line is a label for « your Claude acts on this »; it is not a name your Claude must carry.

## Optional

- `--with-map`: the product map's page (`map-view`). The map itself is plain JSON files in your repository
  (`map_dir` in your client file): one file per collection, versioned by git. Without the flag the briefs simply have no
  map row to quote.
- Loop timers (`loops due --wake`) and a tmux session per client: not wired. If you want a session woken on a date,
  say so, and your Claude can add a timer of your own.

## Stays out, and why

- `scout-row`: it scores and records into Iphtah's queue (`queue-tick`), the queue of map writes (`map-writes`) and the
  owners' hours (`people`), so without them it would be a different tool. The gesture stays yours: scout with
  `templates/scout-brief.txt` and your Claude, and record the answer on your map row or in the lot's brief.
- The parts of `ship-lot` that need them: ticket registration, the map write, the owner's message, the hours rule and
  `--review-clean`.

- The channel to a person's phone and every other message tool: a message that leaves your machine in someone's name is
  yours to decide, and the floor is « no channel » (a promise that waits for someone is shown in your loops).
- The owner's hours and people, high-speed mode, the quota line and the queue with its timers: they describe Iphtah's
  own team and machine.
- Iphtah's rented build machine and the full-suite gate that sends builds there.
- The registry and the ledger repository: they hold other clients' work. Your ledger is your own file.

## Upgrading

Run the installer again. Files are refreshed, hooks are only added, your `done.json` and `works-for.md` are never
replaced, and `WHATS-NEW.md` lists what changed.
