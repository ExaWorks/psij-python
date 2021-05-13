# Contribution Guide

This project welcomes all contributors. This short guide (based loosely on [
Collective Code Construction Contract](http://zeromq-rfc.wikidot.com/spec:22)
and [matplotlib's development
workflow](https://matplotlib.org/stable/devel/gitwash/development_workflow.html#development-workflow))
details how to contribute in a standardized and efficient manner.

## Git Workflow Summary

- Ensure that you've opened an Issue on Github and consensus around the
  solution has be reached.
  - Minor changes (e.g., grammatical fixes) do not require an Issue first.
- [Create your own
  fork](https://docs.github.com/en/github/getting-started-with-github/fork-a-repo).
- When you are starting a new set of changes, [fetch any changes from the
  upstream
  repo](https://matplotlib.org/stable/devel/gitwash/development_workflow.html#update-the-mirror-of-trunk),
  and [start a new feature branch on your fork from
  that](https://matplotlib.org/stable/devel/gitwash/development_workflow.html#make-a-new-feature-branch).
- Make a new branch for each separable set of changes — ["one task, one
  branch"](https://mail.python.org/pipermail/ipython-dev/2010-October/005632.html)
- [Each commit should make one change](https://dev.to/ruanbrandao/how-to-make-good-git-commits-256k).
  to aide reviewing and (in the worst case) simplify reverting it in the future.
  - A patch commit message should consist of a single short (less than 50
    character) line summarizing the change, optionally followed by a blank line
    and then a more thorough description.
  - Where applicable, a PR or commit message body should reference an Issue by
    number (e.g. `Fixes #33`).
- If you can possibly avoid it, avoid merging upstream branches or any other
  branches into your feature branch while you are working.
  - If you do find yourself merging from upstream, consider [Rebasing on
    upstream](https://matplotlib.org/stable/devel/gitwash/development_workflow.html#rebase-on-trunk).
- Submit a Pull Request from your feature branch against upstream.
  - Use the Draft PR feature on Github or title your PR with `WIP` if your PR is
    not ready for a complete review immediately upon submission.
- Ask on the [Exaworks slack](https://exaworks.slack.com) if you get stuck.


## Pull Request (PR) Merging Process

- PR reviews should be timely. Both reviewer and PR issuer should make a good
  attempt at resolving the conversation as quickly as possible.
- PR reviews exist to check obvious things aren't missed, not to achieve
  perfection.
- A PR is eligible for merging if it has at least one approval from a
  project maintainer, no outstanding requested changes or discussions, and passes
  CI tests (if configured for the repository).
- Discussions created via an inline comment on GitHub should only be "resolved"
  by whomever opened the discussion.
- The person to mark the last open discussion "resolved" should also merge the
  PR ("close the door when you leave"), unless a merge bot is configured for the
  repository, in which case the PR should be left for the bot to merge.
- Maintainers should not merge their own patches except in exceptional cases.

## Code Style

All code should conform to [PEP8](https://www.python.org/dev/peps/pep-0008/).
This compliance can be checked with `make stylecheck` or `make checks` and
be automatically achieved by running `make style`, which runs `autopep8`
under-the-hood. PEP8 compliance is also verified as part of the CI by `flake8`.

## Type Annotations

As much python code in this repo as is feasible should include type annotations.
These type annotations can then be ingested and checked by `mypy`, which can be
run with `make typecheck` and `make checks`.
