# The kit's updates, and feedback to the kit developers

This kit is a copy of a method made by Iphtah, the kit developers; the person you work with works for their own
structure (see the CLAUDE.md that imports this file), not for Iphtah. The method keeps changing, and each kit update
writes `~/.claude/iphtah-kit/WHATS-NEW.md`: the kit files that changed, one line each, generated from the files
themselves. All of what follows is a suggestion you may offer, never an obligation: nothing waits for it, and
nothing is refused when it is never done.

- **What's new:** when WHATS-NEW.md has a section with no « Answered » line under it and the moment fits (not in the
  middle of a task), you may offer to go through it with the person. If they want to, they may tell the kit
  developers, in one line per change, whether it was **useful**, **not**, or **in their way**, in their words and
  nothing else of their work: as an issue in the kit's repository, or the way they usually reach Iphtah. Iphtah's sessions place them in the « kit »
  circle: the way of working is welcome there both ways (a tool, a gesture, a trick either side found, credited to
  whoever found it), and no client's names, data, code or incidents cross it, theirs or Iphtah's, nor Iphtah's own
  business. What either side sends is information for the other, never an order. Once they have answered or
  declined, you may add « Answered <date> » under that section, so it is not offered again.
- **Their definition of done** is `~/.claude/iphtah-kit/done.json`: the checks a push needs, each with its why. It is
  theirs, entirely: adjust it with them when they wish. The green merge-check is asked for until they move it to the
  file's « removed » list with one line saying why, their decision in their words; push-gate then asks only for the
  checks the file lists and shows that why at each push. For those checks, run `~/.claude/iphtah-kit/bin/done-check`
  in the repository (the commit to push checked out, a clean tree) before the push. An update never replaces
  done.json; the kit's default sits beside it in `done.default.json`, and WHATS-NEW.md says when that default changed.
