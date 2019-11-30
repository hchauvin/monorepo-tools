# `monorepo-tools`: Monorepo administration

[![CircleCI](https://circleci.com/gh/hchauvin/monorepo-tools/tree/master.svg?style=svg)](https://circleci.com/gh/hchauvin/monorepo-tools/tree/master)
[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fhchauvin%2Fmonorepo-tools.svg?type=shield)](https://app.fossa.io/projects/git%2Bgithub.com%2Fhchauvin%2Fmonorepo-tools?ref=badge_shield)

`monorepo-tools` aims at offering a collection of tools to administrate a
monorepo.  Monorepos have
[many advantages](https://en.wikipedia.org/wiki/Monorepo) for closed-source systems
as compared to separate repos, and are a sound evolution or starting point for projects
in need of large-scale code refactoring, collaboration, and ease of code
reuse.  A monorepo correctly set up can diminish friction both for
fledging startups, and for companies maintaining, evolving or migrating
legacy projects: they can be introduced at all stages of a product's lifecycle.

The tools can be either consumed using a Command-Line Interface (CLI),
or programmatically.  They are written in Python, packaged in a runnable ZIP
file, and compatible with Python 2.7 and Python 3.7.  Prepackaged runnable
ZIP files are available
[on the release page](https://github.com/hchauvin/monorepo-tools/releases).
Tests are continuously run on Windows, Linux, and Mac OSX.

Right now, `monorepo-tools` only offers one subcommand, `import`, but other
commands will follow.  The scope will be vendoring, open sourcing part of
a monorepo with an OSS-monorepo sync, and related topics.  We plan on
open-sourcing separately some work on continuous integration and 
deployment pipelines for monorepos, as CI/CD is out-of-scope for this project.
Currently only Git is supported as a Version Control System and no plan
is made to extend support to other VCS such as Mercurial.

## Installation

For CLI use, please go to [the release page](https://github.com/hchauvin/monorepo-tools/releases)
and download the appropriate ZIP bundle for your platform.  For Windows,
please make sure that you have Python 2 or Python 3 installed.  On Windows, we
recommend installing Python using [Chocolatey](https://chocolatey.org) (respectively,
with `choco install python2` and `choco install python`).  Usage can be queried with:

```bash
python monorepo_tools.zip --help
```

For programmatic access, use [bazel](https://bazel.build/) and import
this project in your workspace.

## `monorepo_tools-import`

```
usage: monorepo_tools import [-h] --individual_repos INDIVIDUAL_REPOS
                             --dest_branch DEST_BRANCH --monorepo_path
                             MONOREPO_PATH

Import individual repos into a monorepo

optional arguments:
  -h, --help            show this help message and exit
  --individual_repos INDIVIDUAL_REPOS
                        Path to python module that exports one function,
                        individual_repos, that takes the destination branch
                        name as an argument
  --dest_branch DEST_BRANCH
                        The destination branch to import into
  --monorepo_path MONOREPO_PATH
                        The local path to the monorepo (it is created if it
                        does not exist)
```

Note that incremental update of an existing monorepo is supported, just
set `--monorepo_path` to a clone.

See [./import_into/individual_repos.py]() for an example for `--individual_repos`.

The strategy for `import` is "merge unrelated history then move": for each
individual repo, we create in the monorepo a branch that is the result
of pulling the unrelated history from the requested branch in the individual
repo.  This history is directly taken from the individual repo, without
any transformation, meaning that the commit SHA1 are the same, which helps
for traceability and auditing.  Additionally, because there is no
transformation, the import is faster than other strategies (see below).
The files in this branch are moved to the appropriate subdirectory of the
monorepo (and these moves are committed), then this branch is merged into
the destination monorepo branch.  This way, `import` introduces two
additional commits per individual repo and destination branch: a move,
and a merge.  Additionally, `import` provides the first commit in the
monorepo branch (with the message "Initial monorepo commit"), onto which
the individual repos are grafted.  With this strategy, commit history is best
viewed in date order, not ancestor order.

### Alternatives

While researching `import`, other strategies and tools were looked at.  We
specifically wanted a tool that would allow the complete import of histories,
and autonomy of the monorepo from the separate repos.  Therefore, Git
[submodules](https://git-scm.com/book/en/v2/Git-Tools-Submodules)
and [`git-subrepo`](https://github.com/ingydotnet/git-subrepo) were taken
out of the picture, as they work by maintaining references to the separate repos.

Next, [Copybara](https://github.com/google/copybara) was
considered.  However, its iterative filtering strategy is a huge
performance issue for large separate repos, and it was quickly abandoned,
as a full migration of the repos we were considering would take Copybara
many days to perform.

[`git-stitch-repo`](https://metacpan.org/pod/git-stitch-repo)
was also considered.  It nicely uses `git-fast-import` and `git-fast-export`
to combine linear histories into one linear history, which could be cleaner 
than our "merge unrelated history then move" (as it comes with merge "nonlinearities").
However, we found out that `git-stitch-repo` gave wrong results for nonlinear histories, as
the commits were sometimes not correctly stitched.  The project, written in Perl, had not
been maintained for years.  We also decided that Git history
rewriting was too difficult to get right for the mixed benefits
of enforcing a linear Git history.  That's why we went back to the
very simple strategy than ended up being `import` and didn't try to patch
`git-stitch-repo` instead.

## License

`monorepo-tools` is licensed under [The MIT License](./LICENSE).


[![FOSSA Status](https://app.fossa.io/api/projects/git%2Bgithub.com%2Fhchauvin%2Fmonorepo-tools.svg?type=large)](https://app.fossa.io/projects/git%2Bgithub.com%2Fhchauvin%2Fmonorepo-tools?ref=badge_large)