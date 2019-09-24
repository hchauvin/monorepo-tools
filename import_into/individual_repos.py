# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Example individual repos for end-to-end tests.  This file
is sourced by the CLI and by `e2e_test.py` directly.
"""
from monorepo_tools.import_into import IndividualRepo


def individual_repos(dest_branch_name):
  # This test that the CLI did pass the correct destination branch name
  assert dest_branch_name == "stitched"

  # These repos and branches have been arbitrarily chosen
  return [
      IndividualRepo(
          location = "https://github.com/reduxjs/redux.git",
          branch = "v4.0.4",
          name = "redux",
          destination = "packages/redux/core",
      ),
      IndividualRepo(
          location = "https://github.com/acdlite/recompose.git",
          branch = "v0.30.0",
          name = "recompose",
          destination = "packages/recompose",
      ),
  ]
