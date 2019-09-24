# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Unit tests for the `import_into` module."""
import unittest
import os
import re
import attr
import shutil
from git import Repo, Actor, NULL_TREE
from monorepo_tools.common.pathutils import onerror
from monorepo_tools.import_into import import_into_monorepo, IndividualRepo
from testutils import (REPOS_ROOT, ExpectedCommits, ExpectedCommit,
                       ExpectedDiff, repo_file, debug_repos)

#: If `True`, displays a summary of the repos on test case tear down.
DEBUG = False


class ImportTest(unittest.TestCase):

  def setUp(self):
    # Removing the `REPOS_ROOT` dir tree here instead of in `tearDown`
    # allows post-mortem inspection when combined with the Bazel
    # CLI argument `--sandbox_debug`.
    if os.path.exists(REPOS_ROOT):
      shutil.rmtree(REPOS_ROOT, onerror = onerror)
    os.mkdir(REPOS_ROOT)

  def tearDown(self):
    if DEBUG:
      debug_repos()

  def test_two_individual_repos_can_be_merged(self):
    monorepo = Repo.init(os.path.join(REPOS_ROOT, "monorepo"))
    repo1 = init_repo1()
    repo2 = init_repo2()
    import_into_monorepo(
        monorepo, [repo1, repo2], "develop", silent = not DEBUG)
    self.assertSetEqual(
        set([repr(ref) for ref in monorepo.refs]),
        set([
            '<git.Head "refs/heads/develop">',
            '<git.RemoteReference "refs/remotes/repo2/master2">',
            '<git.Head "refs/heads/individual_repos/develop/repo2">',
            '<git.Head "refs/heads/individual_repos/develop/repo1">',
            '<git.RemoteReference "refs/remotes/repo1/master1">',
            '<git.Head "refs/heads/master">'
        ]))
    expected_commits = TWO_INDIVIDUAL_REPOS_EXPECTED_COMMITS
    self.assert_commits_equal(
        expected_commits,
        [commit for commit in monorepo.iter_commits("develop")])
    self.assertEqual(
        expected_commits.match_head(monorepo, "develop"), "MERGE_MOVED_REPO2")

  def test_no_commit_if_the_individual_repo_did_not_change(self):
    monorepo = Repo.init(os.path.join(REPOS_ROOT, "monorepo"))
    repo1 = init_repo1()
    repo2 = init_repo2()
    import_into_monorepo(
        monorepo, [repo1, repo2], "develop", silent = not DEBUG)
    commit_before = monorepo.rev_parse("develop")
    import_into_monorepo(
        monorepo, [repo1, repo2], "develop", silent = not DEBUG)
    commit_after = monorepo.rev_parse("develop")
    self.assertEqual(commit_before.hexsha, commit_after.hexsha)

  def test_incremental_merge_if_the_individual_repo_changed(self):
    monorepo = Repo.init(os.path.join(REPOS_ROOT, "monorepo"))
    repo1 = init_repo1()
    import_into_monorepo(monorepo, [repo1], "develop", silent = not DEBUG)

    repo1_git = Repo(repo1.location)
    repo_file(repo1_git, "qux.txt", "QUX")
    repo1_git.index.add([os.path.join(repo1_git.working_dir, "qux.txt")])
    commit = repo1_git.index.commit(
        "Commit 2",
        committer = Actor("Committer2", "committer2@domain.test"),
        author = Actor("Author2", "author1@domain.test"))
    repo1_git.heads["master1"].commit = commit

    import_into_monorepo(monorepo, [repo1], "develop", silent = not DEBUG)

    commits = [commit for commit in monorepo.iter_commits("develop")]
    expected_commits = INCREMENTAL_MERGE_EXPECTED_COMMITS
    self.assert_commits_equal(expected_commits, commits)
    self.assertEqual(
        expected_commits.match_head(monorepo, "develop"), "MERGE_MOVED_REPO1_2")

  def test_adding_an_individual_repo_after_another(self):
    monorepo = Repo.init(os.path.join(REPOS_ROOT, "monorepo"))
    repo1 = init_repo1()
    repo2 = init_repo2()
    import_into_monorepo(monorepo, [repo1], "develop", silent = not DEBUG)
    import_into_monorepo(
        monorepo, [repo1, repo2], "develop", silent = not DEBUG)

    commits = [commit for commit in monorepo.iter_commits("develop")]
    expected_commits = TWO_INDIVIDUAL_REPOS_EXPECTED_COMMITS
    self.assert_commits_equal(expected_commits, commits)
    self.assertEqual(
        expected_commits.match_head(monorepo, "develop"), "MERGE_MOVED_REPO2")

  def assert_commits_equal(self, expected_commits, actual_commits):
    # The number of commits must be the same
    self.assertEqual(len(expected_commits.commits), len(actual_commits))

    # We associate commit hexsha to the names that the commits are
    # given in the fixture.
    commit_hexsha_to_names = {
        actual_commit.hexsha: expected_commits.match(actual_commit)[0]
        for actual_commit in actual_commits
    }

    for actual_commit in actual_commits:
      # The actual commit is matched against an expected commit
      (commit_name, expected_commit) = expected_commits.match(actual_commit)

      if expected_commit.committer:
        self.assertEqual(actual_commit.committer.name,
                         expected_commit.committer,
                         "unexpected committer for {} (sha: {})".format(
                             commit_name, actual_commit.hexsha))
      if expected_commit.author:
        self.assertEqual(actual_commit.author.name, expected_commit.author,
                         "unexpected author for {} (sha: {})".format(
                             commit_name, actual_commit.hexsha))
      if expected_commit.parents:
        expected = set(expected_commit.parents)
        actual = set([
            commit_hexsha_to_names[str(commit)]
            for commit in actual_commit.parents
        ])
        self.assertSetEqual(expected, actual,
                            ("unexpected commit parents for {} (sha: {})\n" +
                             "expected: {}\nactual: {}").format(
                                 commit_name,
                                 actual_commit.hexsha,
                                 expected,
                                 actual,
                             ))
      if expected_commit.diffs_against_null_tree:
        expected = set(expected_commit.diffs_against_null_tree)
        actual = set([
            ExpectedDiff(
                change_type = diff.change_type,
                a = (diff.a_path, diff.a_blob.data_stream.read())
                if diff.a_blob else None,
                b = (diff.b_path, diff.b_blob.data_stream.read())
                if diff.b_blob else None,
            ) for diff in actual_commit.diff(NULL_TREE)
        ])
        self.assertSetEqual(expected, actual,
                            ("unexpected diffs for {} (sha: {})\n" +
                             "expected: {}\nactual: {}").format(
                                 commit_name,
                                 actual_commit.hexsha,
                                 expected,
                                 actual,
                             ))


def init_repo1():
  repo = Repo.init(os.path.join(REPOS_ROOT, "repo1"))
  repo_file(repo, "foo.txt", "FOO")
  repo.index.add([os.path.join(repo.working_dir, "foo.txt")])
  commit = repo.index.commit(
      "Commit 1",
      committer = Actor("Committer1", "committer1@domain.test"),
      author = Actor("Author1", "author1@domain.test"))
  repo.create_head("master1", commit)
  return IndividualRepo(repo.working_dir, "master1")


def init_repo2():
  repo = Repo.init(os.path.join(REPOS_ROOT, "repo2"))
  repo_file(repo, "bar.txt", "BAR")
  repo.index.add([os.path.join(repo.working_dir, "bar.txt")])
  commit = repo.index.commit(
      "Commit 2",
      committer = Actor("Committer2", "committer2@domain.test"),
      author = Actor("Author2", "author2@domain.test"))
  repo.create_head("master2", commit)
  return IndividualRepo(repo.working_dir, "master2")


TWO_INDIVIDUAL_REPOS_EXPECTED_COMMITS = ExpectedCommits({
    "INIT_MONOREPO":
        ExpectedCommit(
            message = "Initial monorepo commit",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = [],
            diffs_against_null_tree = [],
        ),
    "INIT_REPO1":
        ExpectedCommit(
            message = "Commit 1",
            committer = "Committer1",
            author = "Author1",
            parents = [],
            diffs_against_null_tree = [
                ExpectedDiff(change_type = 'A', b = ('foo.txt', b'FOO')),
            ],
        ),
    "INIT_REPO2":
        ExpectedCommit(
            message = "Commit 2",
            committer = "Committer2",
            author = "Author2",
            parents = [],
            diffs_against_null_tree = [
                ExpectedDiff(change_type = 'A', b = ('bar.txt', b'BAR')),
            ],
        ),
    "PULL_REPO1":
        ExpectedCommit(
            message = re.compile(r"^Merge branch 'master1' of .*$"),
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["INIT_MONOREPO", "INIT_REPO1"],
            diffs_against_null_tree = [],
        ),
    "PULL_REPO2":
        ExpectedCommit(
            message = re.compile(r"^Merge branch 'master2' of .*$"),
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["INIT_MONOREPO", "INIT_REPO2"],
            diffs_against_null_tree = [],
        ),
    "MOVE_FILES_REPO1":
        ExpectedCommit(
            message = "Move files from repo repo1 to directory repo1",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["PULL_REPO1"],
            diffs_against_null_tree = [
                ExpectedDiff(
                    change_type = 'R',
                    a = ('foo.txt', b'FOO'),
                    b = ('repo1/foo.txt', b'FOO'),
                ),
            ],
        ),
    "MOVE_FILES_REPO2":
        ExpectedCommit(
            message = "Move files from repo repo2 to directory repo2",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["PULL_REPO2"],
            diffs_against_null_tree = [
                ExpectedDiff(
                    change_type = 'R',
                    a = ('bar.txt', b'BAR'),
                    b = ('repo2/bar.txt', b'BAR'),
                ),
            ],
        ),
    "MERGE_MOVED_REPO1":
        ExpectedCommit(
            message = "Merge repo repo1",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["MOVE_FILES_REPO1", "INIT_MONOREPO"],
            diffs_against_null_tree = [],
        ),
    "MERGE_MOVED_REPO2":
        ExpectedCommit(
            message = "Merge repo repo2",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["MOVE_FILES_REPO2", "MERGE_MOVED_REPO1"],
            diffs_against_null_tree = [],
        )
})

INCREMENTAL_MERGE_EXPECTED_COMMITS = ExpectedCommits({
    "INIT_MONOREPO":
        ExpectedCommit(
            message = "Initial monorepo commit",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = [],
            diffs_against_null_tree = [],
        ),
    "INIT_REPO1":
        ExpectedCommit(
            message = "Commit 1",
            committer = "Committer1",
            author = "Author1",
            parents = [],
            diffs_against_null_tree = [
                ExpectedDiff(change_type = 'A', b = ('foo.txt', b'FOO')),
            ],
        ),
    "PULL_REPO1_1":
        ExpectedCommit(
            message = re.compile(r"^Merge branch 'master1' of .*$"),
            name_rev = "individual_repos/develop/repo1~3",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["INIT_MONOREPO", "INIT_REPO1"],
            diffs_against_null_tree = [],
        ),
    "MOVE_FILES_REPO1_1":
        ExpectedCommit(
            message = "Move files from repo repo1 to directory repo1",
            name_rev = "individual_repos/develop/repo1~2",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["PULL_REPO1_1"],
            diffs_against_null_tree = [
                ExpectedDiff(
                    change_type = 'R',
                    a = ('foo.txt', b'FOO'),
                    b = ('repo1/foo.txt', b'FOO'),
                ),
            ],
        ),
    "MERGE_MOVED_REPO1_1":
        ExpectedCommit(
            message = "Merge repo repo1",
            name_rev = "develop^2",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["MOVE_FILES_REPO1_1", "INIT_MONOREPO"],
            diffs_against_null_tree = [],
        ),
    "NEXT_COMMIT_REPO1":
        ExpectedCommit(
            message = "Commit 2",
            committer = "Committer2",
            author = "Author2",
            parents = [],
            diffs_against_null_tree = [
                ExpectedDiff(change_type = 'A', b = ('qux.txt', b'QUX')),
            ],
        ),
    "PULL_REPO1_2":
        ExpectedCommit(
            message = re.compile(r"^Merge branch 'master1' of .*$"),
            name_rev = "individual_repos/develop/repo1~1",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["MOVE_FILES_REPO1_1", "NEXT_COMMIT_REPO1"],
            diffs_against_null_tree = [],
        ),
    "MOVE_FILES_REPO1_2":
        ExpectedCommit(
            message = "Move files from repo repo1 to directory repo1",
            name_rev = "individual_repos/develop/repo1",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["PULL_REPO1_2"],
            diffs_against_null_tree = [
                ExpectedDiff(
                    change_type = 'R',
                    a = ('qux.txt', b'QUX'),
                    b = ('repo1/qux.txt', b'QUX'),
                ),
            ],
        ),
    "MERGE_MOVED_REPO1_2":
        ExpectedCommit(
            message = "Merge repo repo1",
            name_rev = "develop",
            committer = "monorepo-tools",
            author = "monorepo-tools",
            parents = ["MOVE_FILES_REPO1_2", "MERGE_MOVED_REPO1_1"],
            diffs_against_null_tree = [],
        ),
})

if __name__ == "__main__":
  unittest.main()
