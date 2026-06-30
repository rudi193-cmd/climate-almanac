# Stewarding an Almanac vertical

This catalog is a community-maintained index of public datasets in its domain — a map of where
the data lives, not a copy of the data itself. Each entry is one small YAML file pointing to an
authoritative source, with how to access it and whether it's still reachable. A daily job
re-checks every link and flags anything that's gone dark.

As steward, you own the *contents*, not the machinery. The engine — schema, validation, the
reachability monitor — is shared across all of The Almanac's verticals and maintained upstream;
you don't touch it. Your job is curation judgment: approve good entries, keep statuses honest,
and decide what's worth cataloging.

Day to day that means: reviewing the "Suggest a dataset" issues people file (they don't need to
write code — you turn the form into a catalog entry, or merge their PR), confirming a source
actually resolves before you mark it `live`, and triaging the dead-link alerts the monitor opens.
The one rule that defines the project: **catalog, don't host** — never commit data files, only
records pointing to them.

Two principles carry the whole thing: **authoritative sources only** (the publisher's canonical
home, never a reposting) and **accuracy over coverage** (a small, current, correct catalog beats
a big stale one). When unsure something is verifiable, under-claim.

Everything you need is in the repo: `CONTRIBUTING.md` for the entry checklist, `AGENTS.md` for the
schema invariants, and `SETUP.md` for the one-time configuration. Start by reading the entries
already in `catalog/` — they're the template for everything else.


## Becoming a steward

Stewardship is earned, not assigned. The usual path: land a clean catalog PR or
two — a well-formed entry, an honest `status`, a verified source — and you've
already done the job. If you'd like to own a vertical, say so in an issue or on a
PR and a caretaker will set you up.

What being a steward grants, concretely:

- A seat on the vertical's GitHub team, `@almanac-data/<vertical>-stewards`.
- Code-owner review rights: PRs touching `catalog/` request your review
  automatically, and `main` won't merge without a code-owner approval.
- The standing to merge other contributors' entries on your own judgment.

You never gain — or need — write access to the engine. Schema, validation, and
the reachability monitor stay upstream and shared across every vertical.

## How onboarding works (for the caretaker)

Each vertical's `main` is branch-protected identically: the `validate` CI check
must pass (strict / branch up to date), and **one code-owner approval** is
required to merge. Code owners live in `.github/CODEOWNERS`. Until a vertical has
stewards, that file points the catch-all (`*`) at the engine caretaker, so every
PR still auto-requests a reviewer and nothing merges unreviewed. Admins are
exempt from the rules (`enforce_admins: false`) so the caretaker can still push
a direct hotfix when needed.

To bring a steward onboard:

1. **Create the team** (once per vertical): `@almanac-data/<vertical>-stewards`,
   and add the person to it.
2. **Scope ownership** in `.github/CODEOWNERS` — replace the catch-all with the
   area they own, keeping engine paths with the caretaker:
   ```
   /catalog/   @almanac-data/<vertical>-stewards
   /schema/    @rudi193-cmd
   /scripts/   @rudi193-cmd
   /.github/   @rudi193-cmd
   ```
3. That's it. GitHub now routes catalog PRs to the steward team and blocks merge
   until one of them approves; engine changes still route to the caretaker.

The only per-vertical difference is who's named in CODEOWNERS — the protection
rules themselves are uniform across the org.
