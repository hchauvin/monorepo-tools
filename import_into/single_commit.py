# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.
"""Importing algorithm that creates a single commit with all
the files coming from the individual directories.

This algorithm discards history, but is useful for testing purposes.
"""
import os
import logging
import tempfile
import shutil
import subprocess
from git import Repo, Actor
from monorepo_tools.import_into import IndividualRepo

DEFAULT_AUTHOR = Actor("monorepo-tools", "monorepo-tools@chauvin.io")
DEFAULT_COMMITTER = DEFAULT_AUTHOR
DEFAULT_LOGGER_NAME = "monorepo"
TEMP_ROOT_DIR = "~/.monorepo-tools"


def single_commit(monorepo,
                  individual_repos,
                  dest_branch_name = "master",
                  workdir = None,
                  silent = False,
                  author = DEFAULT_AUTHOR,
                  committer = DEFAULT_COMMITTER,
                  logger_name = DEFAULT_LOGGER_NAME):
  """Imports individual repos into a monorepo using a "single commit" strategy.
  The history of the individual repos is discarded.

  Args:
    monorepo: Monorepo object, of type `git.Repo`, to import into.
    individual_repos: List of individual repos, of type `IndividualRepo`.
    dest_branch_name: The destination branch to put the individual repos in.
    workdir: The working directory where to put the shallow clones of the
      individual repos.  By default, a temporary directory is created.
    silent: Whether to suppress all progress report.
    author: The author to use when the import algorithm creates commits.
    committer: The committer to use when the import algorithm creates commits.
    logger_name: The `logging` logger name to use for all progress reports.
  """
  syncer = _SingleCommit(monorepo, individual_repos, author, committer,
                         logger_name)
  if silent:
    syncer.logger.setLevel(logging.WARNING)

  temp_workdir_holder = None
  if not workdir:
    temp_root_dir = os.path.expanduser(TEMP_ROOT_DIR)
    if not os.path.exists(temp_root_dir):
      os.mkdir(temp_root_dir)
    temp_workdir_holder = tempfile.TemporaryDirectory(dir = temp_root_dir)
    workdir = temp_workdir_holder.name
  try:
    syncer.clone_single_branches(workdir)
    syncer.copy(workdir)
  finally:
    if temp_workdir_holder:
      temp_workdir_holder.cleanup()
  syncer.create_dest_branch(dest_branch_name)
  syncer.logger.info("Done")


class _SingleCommit:

  def __init__(self, monorepo, individual_repos, author, committer,
               logger_name):
    self.logger = logging.getLogger(logger_name)
    self.monorepo = monorepo
    self.individual_repos = individual_repos
    self.author = author
    self.committer = committer

    self._init_environ()
    self._init_logger()

  def _init_environ(self):
    # We need this because some commands (e.g. `pull`) do not allow for
    # author/committer override.
    os.environ["GIT_AUTHOR_NAME"] = self.author.name
    os.environ["GIT_AUTHOR_EMAIL"] = self.author.email
    os.environ["GIT_COMMITTER_NAME"] = self.committer.name
    os.environ["GIT_COMMITTER_EMAIL"] = self.committer.email

  def _init_logger(self):
    self.logger.setLevel(logging.INFO)
    self.logger.handlers = [
        h for h in self.logger.handlers
        if not isinstance(h, logging.StreamHandler)
    ]
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("+%(relativeCreated)dms - %(message)s"))
    self.logger.addHandler(ch)

  def clone_single_branches(self, workdir):
    self.logger.info("Clone single branches...")
    for individual_repo in self.individual_repos:
      self.logger.info("For {}: {}".format(individual_repo.name,
                                           individual_repo.branch))
      Repo.clone_from(
          individual_repo.location,
          os.path.join(workdir, individual_repo.name),
          single_branch = True,
          branch = individual_repo.branch,
          depth = 1)

  def copy(self, workdir):
    self.logger.info("Copying files in individual repos...")
    for individual_repo in self.individual_repos:
      self.logger.info(individual_repo.name)
      shutil.copytree(
          os.path.join(workdir, individual_repo.name),
          os.path.join(self.monorepo.working_dir, individual_repo.destination),
          symlinks = True,
          ignore = shutil.ignore_patterns(".git"))

  def create_dest_branch(self, dest_branch_name):
    self.logger.info("Create destination branch...")
    self.monorepo.git.checkout("-b", dest_branch_name)
    self.monorepo.git.add("-A")
    self.monorepo.git.commit("-m", "Monorepo commit")
    self.logger.info("Monorepo commit successfully made")
