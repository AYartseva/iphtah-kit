# What's new in the kit

One line per kit file an update changed, newest first; what the person may do with it, if they wish: `feedback.md`.

## Since method cabf13f2 (2026-11-01T18:50:40+00:00), now method d17e3c5a (2026-11-10T14:34:31+00:00, with local changes)

- CONTRIBUTING.md (changed, +3 −0 lines): in « Contributing »; new text: « Questions and bug reports go to https://github.com/AYartseva/iphtah-support: this repository's own … »
- README.md (changed, +26 −5 lines): in « Lean Vibe Coding », « The kit », « What is in it », « First steps, with your Claude », …; new text: « Questions and bug reports go to https://github.com/AYartseva/iphtah-support (this repository's own … »
- agents-codex.md (new, 36 lines): « On Codex »
- bin/_codex_hooks.py (new, 660 lines)
- bin/_hooks_merge.py (new, 107 lines)
- bin/_machine.py (changed, +32 −0 lines): in « limit », « claude_account »
- bin/_purpose.py (changed, +9 −0 lines)
- bin/fix-brief (changed, +1 −1 lines): in « main »
- bin/heavy-gate (changed, +2 −2 lines): in « main »
- bin/iphtah-project (changed, +1 −0 lines): in « main »
- bin/launch-lot (changed, +7 −0 lines): in « main »
- bin/loops (changed, +10 −4 lines): in « check_acts », « due », « main »
- bin/lots (changed, +492 −24 lines): in « agent_files », « text_of », « close », « session_files », …
- bin/magic-number-lint (new, 434 lines)
- bin/merge-check (changed, +40 −7 lines): in « nolock », « show_findings »
- bin/mutant-check (changed, +213 −37 lines): in « select_lines », « summarize », « cap_said », « run_java », …
- bin/open-issues (changed, +9 −4 lines): in « line », « fetch », « main »
- bin/prompt-lines (changed, +1 −1 lines): in « my_due_loops »
- bin/push-gate (changed, +2 −2 lines): in « main »
- bin/review-brief (changed, +5 −3 lines): in « main »
- bin/run-queued (changed, +113 −15 lines): in « queue_dir », « acquire », « held »
- bin/ship-lot (changed, +30 −2 lines): in « repo_of », « main »
- bin/verify-lot (changed, +197 −22 lines): in « lot_containers », « dod_required », « dod_line », « builder_line », …
- codex/dev.agents.md (new, 304 lines): « User-level instructions (written by install.py) »
- codex/dev.deny.json (new, 16 lines)
- codex/dev.hooks.json (new, 88 lines)
- codex/lead-dev.agents.md (new, 293 lines): « User-level instructions (written by install.py) »
- codex/lead-dev.deny.json (new, 9 lines)
- codex/lead-dev.hooks.json (new, 88 lines)
- install.py (changed, +245 −35 lines): in « repo_only », « kit_plan », « load_settings », « dump_settings », …
- llms.txt (changed, +4 −1 lines)
- rituals/brief-and-review-rules.md (changed, +35 −1 lines): in « Build rules (for every agent's brief) », « Severity: how much proof, and when review stops (15/10/2026) », « Review questions (for every fresh-eyes review brief) »; new text: « - « NOT RUN: <reason> » (exit 3, 05/11/2026) means nothing was proved: no test covers the »
- roles/lead-dev.md (changed, +6 −1 lines): in « What you decide », « Reviewing a developer's work »; new text: « - Merging: it depends on the client's project setting `agent_merge`, `never` when it is not written… »
- roles/settings/dev.settings.json (changed, +22 −0 lines)
- roles/settings/lead-dev.settings.json (changed, +31 −0 lines)
- templates/lot-brief.txt (changed, +7 −1 lines)
- tools.md (changed, +1 −1 lines): in « Notes »; new text: « - `acts:agent` in a loop line is a label for « your Claude acts on this »; it is not a name your Cl… »

## Since method 2438adba (2026-11-01T18:13:33+00:00), now method cabf13f2 (2026-11-01T18:50:40+00:00)

- core.md (changed, +1 −1 lines): in « How the kit developers work: life-hacks to adopt, adjust or… »; new text: « Two more, short. **When you think WTF, stop and think:** it is the andon cord; a good surprise carr… »

## Since method e8879958 (2026-11-01T17:53:45+00:00, with local changes), now method 2438adba (2026-11-01T18:13:33+00:00)

- README.md (changed, +1 −1 lines): in « First steps, with your Claude »; new text: « The installer also sets up a user timer, `egress sample` every 5 minutes: what this account's proce… »
- install.py (changed, +6 −5 lines): in « show_install », « egress_units », « enable_egress_timer », « do_uninstall »

## Since method e8879958 (2026-11-01T17:53:45+00:00, with local changes), now method e8879958 (2026-11-01T17:53:45+00:00, with local changes)

- install.py (changed, +2 −1 lines): in « systemctl_user »

## Since method e8879958 (2026-11-01T17:53:45+00:00), now method e8879958 (2026-11-01T17:53:45+00:00, with local changes)

- README.md (changed, +1 −0 lines): in « First steps, with your Claude »; new text: « The installer also sets up a user timer, `egress sample` every 5 minutes: what this account's proce… »
- bin/egress (new, 349 lines)
- install.py (changed, +71 −0 lines): in « show_install », « do_install », « do_uninstall »
- tools.md (changed, +2 −0 lines): in « Notes »; new text: « `egress`: what this account's processes talk to, sampled every 5 minutes by a user timer the instal… »
