# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Utility functions and objects used during unit testing."""
import attr
import os
from git import Repo, NULL_TREE
import re
import sys

#: Where to put all the test repos
REPOS_ROOT = os.path.join(os.environ["TEST_TMPDIR"], "REPOS")


@attr.s(frozen = True)
class ExpectedCommits(object):
  """Sequence of expected commits."""

  #: Dictionary of name to `ExpectedCommit` objects.
  #: Names are used to reference expected commits, e.g. in
  #: `ExpectedCommit.parents`.
  commits = attr.ib()

  def match(self, actual_commit):
    """Tries to match one of the expected commits to an actual commit.

    Args:
      actual_commit: Actual commit, of type `git.Commit`.
    Returns:
      The expected commit.
    Throws:
      `IndexError` if the commit cannot be found.
    """
    stripped_name_rev = actual_commit.name_rev.split()[1]
    for commit in self.commits.items():
      message_match = False
      if sys.version_info >= (3, 0):
        cls = str
      else:
        cls = basestring
      if not isinstance(commit[1].message, cls):
        if commit[1].message.match(actual_commit.message):
          message_match = True
      elif commit[1].message == actual_commit.message:
        message_match = True
      # There is a match if the messages match and either no expected name_rev
      # was specified or the name_revs match.
      if message_match and (not commit[1].name_rev or
                            (commit[1].name_rev == stripped_name_rev)):
        return commit
    raise IndexError("cannot match message '{}' for name rev '{}'".format(
        actual_commit.message, stripped_name_rev))

  def match_head(self, monorepo, name):
    """Matches the head of a ref.  See `ExpectedCommits.match` for details."""
    return self.match(monorepo.rev_parse(name))[0]


@attr.s(frozen = True)
class ExpectedCommit(object):
  """An expected commit."""
  message = attr.ib()
  committer = attr.ib()
  author = attr.ib()
  #: Sequence of commit "names" (see `Commits`).
  parents = attr.ib()
  #: Sequence of `ExpectedDiff` objects.
  diffs_against_null_tree = attr.ib()
  name_rev = attr.ib(default = None)


@attr.s(frozen = True)
class ExpectedDiff(object):
  change_type = attr.ib()
  a = attr.ib(default = None)
  b = attr.ib(default = None)


def repo_file(repo, filename, content):
  with open(os.path.join(repo.working_dir, filename), "w") as f:
    f.write(content)


def debug_repos():
  """Shows debug infos about all the repos."""
  for repo_name in os.listdir(REPOS_ROOT):
    repo = Repo(path = os.path.join(REPOS_ROOT, repo_name))
    print("======================================================")
    print("REPO: {}".format(repo_name))
    print("PATH: {}".format(repo.working_dir))
    for branch in repo.branches:
      print("------------------------------------------------------")
      print("BRANCH: {}".format(branch.name))
      for commit in repo.iter_commits(branch.name):
        stripped_name_rev = commit.name_rev.split()[1]
        print("{} ({}) - {}".format(stripped_name_rev, commit.hexsha,
                                    commit.message))
        print("  Author: {} - committer: {}".format(commit.author,
                                                    commit.committer))
        print("  Parents: {}".format(commit.parents))
        print("  Diff against null tree:")
        for diff in commit.diff(NULL_TREE):
          if diff.a_blob:
            a = (diff.a_path, diff.a_blob.data_stream.read())
          else:
            a = None
          if diff.b_blob:
            b = (diff.b_path, diff.b_blob.data_stream.read())
          else:
            b = None
          print("    {} | A: {} - B: {}".format(diff.change_type, a, b))
