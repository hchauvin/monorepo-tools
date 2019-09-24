# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""End-to-end tests with "real" remote public GitHub repos, and direct
invocation of the `monorepo_tools` CLI."""
import os
import unittest
import shutil
import filecmp
import attr
import time
import subprocess
from rules_python.python.runfiles import runfiles
from git import Repo
from monorepo_tools.import_into import import_into_monorepo
from monorepo_tools.common.pathutils import onerror
from single_commit import single_commit
from individual_repos import individual_repos

REPOS_ROOT = os.path.join(os.environ["TEST_TMPDIR"], "REPOS")


@attr.s(frozen = True)
class Algorithm(object):
  name = attr.ib()
  fun = attr.ib()
  options = attr.ib()


ALGORITHMS = [
    Algorithm(
        name = "import_into_monorepo", fun = import_into_monorepo,
        options = {}),
    Algorithm(
        name = "single_commit",
        fun = single_commit,
        options = {"workdir": os.path.join(REPOS_ROOT, "workdir")}),
]


class E2eTest(unittest.TestCase):

  def setUp(self):
    # Removing the `REPOS_ROOT` dir tree here instead of in `tearDown`
    # allows post-mortem inspection when combined with the Bazel
    # CLI argument `--sandbox_debug`.
    if os.path.exists(REPOS_ROOT):
      shutil.rmtree(REPOS_ROOT, onerror = onerror)
    os.mkdir(REPOS_ROOT)

  def test_working_dir(self):
    dest_branch_name = "stitched"
    repos = individual_repos(dest_branch_name)

    elapsed = {}
    for algorithm in ALGORITHMS:
      start = time.clock()
      monorepo = Repo.init(
          os.path.join(REPOS_ROOT, "monorepo_{}".format(algorithm.name)))
      algorithm.fun(monorepo, repos, dest_branch_name, **algorithm.options)
      elapsed[algorithm.name] = time.clock() - start

    print("ELAPSED (in seconds): {}".format(elapsed))

    # Expect the working dirs to all be the same
    ref_algorithm = ALGORITHMS[0]
    for algorithm in ALGORITHMS[1:]:
      if not is_same(
          os.path.join(REPOS_ROOT, "monorepo_{}".format(ref_algorithm.name)),
          os.path.join(REPOS_ROOT, "monorepo_{}".format(algorithm.name))):
        raise Exception(("monorepo for {} does not have the same working " +
                         "dir as {}").format(algorithm.name,
                                             ref_algorithm.name))

  def test_cli(self):
    """Tests launching the CLI."""
    r = runfiles.Create()
    sp = subprocess.Popen(
        [
            "python",
            r.Rlocation("monorepo_tools/monorepo_tools.zip"), "import",
            "--individual_repos",
            r.Rlocation("monorepo_tools/import_into/individual_repos.py"),
            "--dest_branch", "stitched", "--monorepo_path",
            os.path.join(REPOS_ROOT, "monorepo")
        ],
        stdout = subprocess.PIPE,
        stderr = subprocess.PIPE)
    out, err = sp.communicate()
    if sp.returncode != 0:
      raise Exception(
          "non-zero return code {};\nstdout:\n{}\nstderr:\n{}".format(
              sp.returncode, out.decode('utf8'), err.decode('utf8')))


class dircmp(filecmp.dircmp):
  """
    Compare the content of dir1 and dir2. In contrast with filecmp.dircmp, this
    subclass compares the content of files with the same path.
    """

  def phase3(self):
    """
        Find out differences between common files.
        Ensure we are using content comparison with shallow=False.
        """
    fcomp = filecmp.cmpfiles(
        self.left, self.right, self.common_files, shallow = False)
    self.same_files, self.diff_files, self.funny_files = fcomp


def is_same(dir1, dir2):
  """
    Compare two directory trees content.
    Return False if they differ, True is they are the same.
    """
  compared = dircmp(dir1, dir2, ignore = [".git"])
  if (compared.left_only or compared.right_only or compared.diff_files or
      compared.funny_files):
    compared.report_full_closure()
    return False
  for subdir in compared.common_dirs:
    if not is_same(os.path.join(dir1, subdir), os.path.join(dir2, subdir)):
      return False
  return True


if __name__ == "__main__":
  unittest.main()
