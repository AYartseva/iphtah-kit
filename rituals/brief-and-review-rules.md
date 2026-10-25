# Brief and review rules

Started 05/10/2026 from a count, not from memory: the defects that fresh-eyes reviews found in our own code before
push, sorted by kind. The most frequent kinds were lost updates and double submits, unhandled server answers, false
or missing screen states, guards without proof, rights and scope, and behaviour that differs on the real platform.
A human reviewer still caught, after those reviews, timestamps stored without their zone, missing labels for new
values, and an author deciding their own item.

**How to use it.**
- The lead copies the **build rules** that apply into every agent's brief.
- Every fresh-eyes review brief gets the **review questions**, plus the client's own list of what its reviewers
  caught (method, How we work).

**How it grows.** As the pre-flight checklist does. When a kind keeps coming back after a rule exists, the rule
becomes a mechanical check (a lint, a test, a script). The rule then says which check enforces it.

## The right to challenge (for every brief, build or review)

*Agents follow a brief's framing too readily, and a team of agents that only complies inherits every blind spot of
whoever wrote the brief. So every brief carries this paragraph, verbatim:*

> **You may challenge this brief.** If the brief is wrong, incomplete, or solving the wrong problem, or if you
> see a better way, say so **first**, with evidence (file:line, a command's output, a doc quote), before or
> instead of executing. You may also send **questions for the person** (the product owner): list them in your
> report under « Questions for the person »; the main session relays them as they are and does not answer them
> itself. Disagreeing with evidence is part of the job, not a failure to follow it. Without evidence, follow the
> brief and note your doubt. **Before reporting « blocked » or « impossible »**, spend one pass on how it could
> be done (another tool, another route, a smaller version); report what you tried and what would unlock it.

*The main session's side of the deal:* it reads the challenge before the result, relays the questions as they
are, and when it overrules a challenge it says why in its report to the person.

## Build rules (for every agent's brief)

0. **Related open issues first (08/10/2026).** Issues are written at different granularities (an epic,
   a bug, a one-line idea), so a keyword search is not enough: deciding what is related is a reading job.
   - Before launching, the session runs `bin/open-issues --client C` and gives the agent the path of the list.
   - The agent reads the whole list before building.
   - Its report names each related issue and says whether the lot closes it, advances it, touches it or
     contradicts it.
   - An issue the lot closes gets « Closes owner/repo#n » in the PR body; one it only advances gets
     « Part of … ». Each starts its own line, in the commit message too: queue-tick and lot-close count a claim
     only at a line start, never a mention mid-sentence.

0b. **Reuse before you write (08/10/2026).**
   - Before writing a new table, route, component, rule or tool, search for what already does it, and name it in
     your report: what you reused, and what you wrote only because nothing existed.
   - A new thing that duplicates an existing one is a defect, even if it is better.
   - Rewriting working code is out of scope unless the brief asks for it.
   - When the existing thing is wrong, say so and propose, but don't replace it on your own.

1. **Every remote call lists its answers.** Name what the caller does for success, 401/403, 404, 405, 409, 429, 5xx
   and « unreachable ».
   - Never cache an error as an empty answer.
   - Never let one person's refusal stand for everyone's.
   - Never let one bad item stop a queue: skip it, record it, go on.
2. **Every screen lists its states:** loading, empty, error, denied.
   - Every fact on screen comes from data.
   - « Nothing here » and « could not load » are different messages.
   - A setting shown as off must have been read as off.
3. **No lost update.** A row read and then saved whole overwrites what someone else changed in between. Use a
   version (optimistic lock) or a conditional UPDATE of only the changed columns.
   - A button that starts a save is disabled until its promise settles.
   - A dialog's « OK » returns the promise, never `void`s it.
   - Enforced by `bin/save-check` (05/10/2026): read-then-save-whole in touched Java methods without
     `@Version`, and `onOk` / `onClick` handlers that `void` their promise. Warnings, in merge-check and
     verify-lot.
4. **Bound every list and queue,** and page it with a cursor. A `LIMIT` with no cursor silently hides the rest.
5. **Times carry their zone:** `timestamptz` and instants, never a local timestamp. Test under a non-UTC time zone.
   - In migrations, enforced by `bin/migration-lint` rule M1 (05/10/2026): an error, so merge-check is red.
6. **Rights:** for each gesture, name the right and the scope (the tenant, the project, the person it belongs to) that the SERVER checks.
   The screen gates on that same right, never on a guess of its own.
   - Four eyes: an author never decides their own item.
   - Undoing belongs to the author or a manager, not to anyone who can see the item.
7. **Real platform:**
   - A fake or a fixture may only return fields and routes that the real contract has.
   - A screen that calls a route must know whether that route is deployed (see the pre-flight's deploy-order
     questions).
8. **A new value gets its label** in every locale, wherever values are listed: role matrices, filters, menus.
9. **Files from users are hostile until read** (05/10/2026):
   - parse them in a separate process with a memory limit and a timeout, so a parser crash, a hang or a bomb
     kills one child, never the worker;
   - check the real type from the bytes, not the extension; bound the unpacked size of archives (Office files
     are zips), the page count, and refuse external entities in XML;
   - catch EVERY error per file (not a list of the library's exceptions) and record it against that file.
10. **A machine channel is scoped to one tenant:** a worker asks for one client's (one instance's) work, with that
   client's own identity, and gets read links for that scope only — never a queue across every client.
11. **Proof:** every guard has a negative control. Name the mutant you cut and the test that went red.
    - Mechanical since 09/10/2026: `bin/mutant-check <worktree> --max 10` mutates only the
      lines the branch added, highest-risk first, and runs only the tests that cover them (PIT for Java, Stryker
      for TypeScript; for Python, including the extensionless `bin/` tools, its own line mutators and the unittest
      modules naming the tool, since 13/10/2026: it refuses a dirty tree and restores every file itself, so
      no hand-written mutant script, which is how a builder lost uncommitted work that day); it prints, per
      mutant, KILLED by which test / SURVIVED / NO COVERAGE. Run it before the review and paste its summary line
      in the PR body; a survivor is a guard without proof.
12. **A screen works on a phone** (06/10/2026, when the client asks for it): render every new or changed screen,
   mockups included, at 360, 390 and 768 px, and look at the screenshots. No sideways
   scroll; touch targets of 44 px; a menu that folds instead of filling the first screen; a detail that opens next to
   what was tapped, not below the whole list; bars and tables that keep their meaning when narrow.
13. **One gesture, one rule, for five kinds of hands** (07/10/2026: one « open a file » took four review rounds).
    A web screen is driven by a mouse, a finger, a pen, a keyboard and a screen reader, and each sends different
    events (a finger's double tap can fire `dblclick`; a screen reader may click with no press before it).
    - Decide the rule per kind of input BEFORE building, in one line: « mouse: double-click opens; finger, pen:
      a tap opens; keyboard: Enter opens; screen reader: activation opens ».
    - Use ONE shared helper for the gesture across screens, never a copy per screen (two copies drifted apart).
    - Test the matrix: each kind of input opens exactly once, a stray press cannot block the next one, and an
      action inside the row (star, bin, menu) never opens the row.
    - Name the one check only a real device can do (VoiceOver, TalkBack) in the PR.
14. **Each agent has its own scratch folder** (07/10/2026: two agents both wrote `scratchpad/mutants.py`; one
    agent's run executed the other's script and planted two mutants in its worktree). Every brief names
    `<scratchpad>/<lot>/` as the agent's only scratch folder. Scripts and outputs go there, with names only that
    lot uses; never a bare file at the scratchpad's root.
15. **A guard's side effects come after its verdict** (12/10/2026: three reviews in a row found the decision log
    reopening a gate: a missing function, a stray print, a symlink to the gate's stdout). A gate decides and prints
    its answer first; logging, metrics or notices run after, and cannot reach the channel the answer travels on
    (stdout pointed at /dev/null, files opened without following links or waiting). Test it: break the side effect
    (missing, printing, hanging, hostile path) and the gate's answer and exit code stay identical.
16. **« The manager decided » carries her words** (13/10/2026: a session's own recommendations, sitting in context next
    to her real answers, went into a brief as « Manager answers »; caught on re-read, corrected in a minute). A brief or
    message that says a person decided X quotes their message with its date and time; otherwise it says « my
    recommendation, not yet answered ». A recommendation carried forward is a carried fact, like an old memory line.
17. **A second failure means missing context** (13/10/2026: two lots swung three rounds on one parser). When an agent fails twice on the same thing, the context is missing, not the effort: give it the purpose (what for, against what, what never to block) before a third round. Agents are never the problem, people or models alike (Lean's « people are never problems »): look for the missing context, channel or limit in the process, never for a fault in the agent.
18. **A test removes what it makes** (24/10/2026: 214,000 `/tmp/tmp*` folders, 7.7 GB, left by our tests; the disk reached 98%).
    A temporary folder or file comes from `tempfile.TemporaryDirectory()`,
    or `self.addCleanup(shutil.rmtree, d, True)`; a helper with no `self` registers its own cleanup, a fixture made once per class `cls.addClassCleanup(...)`, once per module `unittest.addModuleCleanup(...)`.

## Severity: how much proof, and when review stops (15/10/2026)

The launch declares a severity; the review reads the **actual** one from what the diff touches, and the higher wins.
Both are recorded: the gap between them is a number worth watching.
`bin/review-brief` reads the actual one from the paths the diff touches (`--severity` for the declared one; a
client adds paths with project.json `severity_high_paths`) and cuts the brief to it: a low lot gets three checks.

| Severity | What puts a lot there | Tests | Review stops |
|---|---|---|---|
| **High** | the diff touches money movements, the rights grid, auth or security config, personal-data deletion, a migration | every guard mutant-proven, with negative controls; the money-rights builder at high effort | when no finding is above minor, or after 3 rounds: then a person decides |
| **Normal** | product behaviour; a gate (push-gate, keep-gate, wa, anything that blocks or sends) | a test per changed behaviour | after one review and the fix of real bugs; edge cases become an issue, not a round |
| **Low** | docs, wording, reports and listings | the build passes | one pass |

A finding that is a rule question (« this guard can be walked around: is that intended? ») is not a build round: it
goes to the decider of that rule as a question. Each round is counted by its cause: a **defect** (our bug), a
**decision** (an answer that arrived after the build, or a question the review raised), or **timing** (merged before
the fix landed). Decision rounds are cut upstream, by asking the rule questions at the scout.

## Review questions (for every fresh-eyes review brief)

- **Probes that load the machine stay small:** a reviewer's or builder's allocation, fork or disk probe on the shared
  VM runs at 64 MiB / a few processes / a few MB at most, inside its own capped scope and under a timeout. Real-size
  load goes to a rented build machine. (24/10/2026: a review probe of the memory cap, 2 GiB under a throttle, stalled the VM for two
  minutes and set off the dead man's switch.)
- **The definition of done first:** the lot brief's fixed block (templates/lot-brief.txt, twelve « must not » lines plus
  the client's `review_catches`) is answered line by line in the report, each with a test or « n/a: why ». Check that
  each answer is true; an unanswered or wrongly « n/a » line is a finding.
- **Worst use** (for any kind of work: code, documents, offers, messages before they leave): what is the worst use of
  this, by accident or on purpose, and does the change make it easier? Name it as a category, never as a working
  recipe. If the worst is acceptable, say go; if not, it is a one-way door for its owner. Reviewers only: builders
  build boldly, and imagining the worst makes them cautious.
- **Concurrency:** a read-then-save-whole? Can a button be pressed twice? Does a dialog return its promise?
- **Errors:** does each remote call handle each status? Is any error cached as « empty »? Can one poison item
  stop the queue?
- **States:** does the screen ever say something false when a load fails, or before it ends?
- **Proof:** which guard has no negative control? Which mutant would survive? (`bin/mutant-check`'s survivors
  and NO COVERAGE lines, when the builder ran it; else run it, `--max 10`, a few minutes.)
- **Hostile files:** is every user file parsed in a bounded child process, typed from its bytes, with archive
  and page bounds? Does any error type escape the per-file catch and stop the loop?
- **Our own oversight guards** (keep-gate, push-gate, test brakes; 13/10/2026: an « act as an attacker » brief was
  stopped by a safety classifier, rightly): review them by a DEFENSIVE reading: the assumptions the guard relies on,
  the categories of input it does not model (named as categories, never as working commands), and whether the tests
  cover each modelled category with a refusal and an allowed case. Never ask for a command that gets through.
- **Gates don't parse the shell** (13/10/2026: two branches each needed three rounds re-fixing a parser that missed
  a new form every time): a gate that reads commands matches a plain pattern and refuses when in doubt; a false
  refusal names how to get through honestly. A patch to a parser's grammar is a sign to change the design.
- **What it is for:** does each part say what it is for (a name, a header, a test that reads as its spec)?
- **Human maintainer** (13/10/2026; only when the project has human
  contributors, project.json `human_contributors`, true by default): could a human maintain this
  without the model? Does the shape follow the problem rather than the generation?
- **Guard order:** can anything a gate does besides deciding (log, metric, notice) change, delay or corrupt its
  answer?
- **Tenancy:** does a machine route or worker see more than one client's or instance's data?
- **Rights:** does the screen gate on the same right and scope as the server? Can an author decide or undo their
  own item?
- **Real platform:** does a fake invent a field or a route? Is a route called before it is deployed?
- **Hands:** for each gesture, does a mouse, a finger, a pen, the keyboard and a screen reader each trigger it
  exactly once? Is the rule in one shared helper?
- **Phone:** was each changed screen rendered at phone widths, and were its screenshots looked at? What does the first
  screen show on a phone?
- **Data:** the same data in two places (one system of record per kind of data)? A list with no bound? A timestamp without zone? A new
  value without its label in every locale? Something the diff writes (a field, column, event, setting, file)
  that no code reads? Written-but-unread is dead work or a missing half (09/10/2026).
  - The two-places question is mechanical since 09/10/2026: `bin/two-sources-lint` warns on a
    list of values (T1) or a named number (T2) the branch adds that another layer already holds, in merge-check
    and verify-lot; a reviewer reads its lines and asks only about what it cannot see (a copy under another name,
    a subset).
- **Migrations:** an exact-count self-check that could stop a boot? A re-added CHECK without `NOT VALID`?
  `CREATE STATISTICS` without `ANALYZE`?
  - Enforced by `bin/migration-lint` (05/10/2026): M2, M4, M3 as warnings; an applied migration modified
    (M5) and a duplicate or too-low number (M6) as errors that turn merge-check red. A finding is accepted
    with `-- lint: allow M<n> <reason>` on its line or the line before.
- **Ownership (07/10/2026):** whose is what this touches (data, content, a key, a name, a licence, a message sent
  in someone's name), and who answers if it harms someone? Being able to do it is not the question: is it ours
  to do, under the agreement, the purpose a key was given for, the licence, the person's consent? Responsibility
  propagates: what the builder does, the manager of the work answers for.
- **Migration numbers:** checked against the open PRs too, not only the base branch. A number free on the base
  can already be taken by someone else's PR waiting for review.
  - Mechanical since 09/10/2026: `bin/migration-lint <worktree> --open-prs` (rule M7, an
    error) names the PR that holds the number and the first free number above the base and every open PR;
    exit 3 when the PRs could not be read, never « clean ». Opt-in: wiring it into merge-check or ship-lot is a
    decision on what blocks a push.
- **Rising without a rule** (Friday review-defects count, 16/10/2026, the first client's session; Data covers dead
  code already):
  - **Stale text:** which comment, migration header or contract sentence does this diff make false?
  - **Contract:** does every sentence of the contract say what the code does?
  - **Input validation:** is each pattern tested with a real accepted value and a real refused one, in the engine
    that runs it?
  - **Data lifecycle:** where does this diff write sensitive data, and who deletes it?
  - **Performance:** which shared resource can this path saturate, and which bound stops it?
- **Suite:** brief the reviewer only on a commit with a green merge-check record. A red suite at review wastes the
  review.

## Writing (for every agent's brief; moved from the method file on 08/10/2026)

- Comments carry the reasoning, not the mechanics: why a decision was taken, what it costs, what would break
  without it, the date and who decided. When a decision is reversed, say so in place rather than deleting the old text.
- Commit attribution names the model that actually wrote the commit.
- Porting or storing a new kind of data: one system of record per data kind, the whole lifecycle, erasure
  included.
