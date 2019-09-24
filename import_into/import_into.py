"""Imports individual repos into a monorepo using a "merge unrelated histories
and move" strategy."""
import logging
import os
# Copyright (c) Hadrien Chauvin
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

from git import Actor
import shutil

DEFAULT_LOGGER_NAME = "monorepo"
DEFAULT_AUTHOR = Actor("monorepo-tools", "monorepo-tools@chauvin.io")
DEFAULT_COMMITTER = DEFAULT_AUTHOR
INITIAL_COMMIT_MESSAGE = "Initial monorepo commit"


def import_into_monorepo(monorepo,
                         individual_repos,
                         dest_branch_name = "master",
                         silent = False,
                         author = DEFAULT_AUTHOR,
                         committer = DEFAULT_COMMITTER,
                         logger_name = DEFAULT_LOGGER_NAME):
  """Imports individual repos into a monorepo using a "merge unrelated histories
  and move" strategy.

  Args:
    monorepo: Monorepo object, of type `git.Repo`, to import into.
    individual_repos: List of individual repos, of type `IndividualRepo`.
    dest_branch_name: The destination branch to put the individual repos in.
    silent: Whether to suppress all progress report.
    author: The author to use when the import algorithm creates commits.
    committer: The committer to use when the import algorithm creates commits.
    logger_name: The `logging` logger name to use for all progress reports.
  """
  syncer = _MonorepoSyncer(monorepo, individual_repos, author, committer,
                           logger_name)
  if silent:
    syncer.logger.setLevel(logging.WARNING)
  syncer.create_remotes()
  to_update = syncer.create_or_update_individual_repo_branches(dest_branch_name)
  syncer.merge_individual_repo_branches(to_update, dest_branch_name)
  syncer.logger.info("Done")


class IndividualRepo:
  """An individual repo to import into a monorepo.

  Attrs:
    location: Location of the individual repo.  Can be remote (`https://...`)
      or a location on the local file system.
    branch: The branch to import.
    name: The name of the monorepo.  Names must be unique across a sequence
      of individual repos to import.  The name is by default the basename
      of the location (if for instance the URL is
      `https://github.com/orga/repo.git`, the `name` is `"repo"`).
    destination: The destination folder, within the monorepo, where to put
      the individual repo.  The destination folder can have multiple parts,
      e.g., `foo/bar`, in which case the subfolders are recursively created.
      The destination folder is by default the `name`.
  """

  def __init__(self, location, branch, name = None, destination = None):
    self.location = location
    self.branch = branch
    self.name = name or _default_repo_name(location)
    self.destination = destination or self.name


class _MonorepoSyncer:

  def __init__(self, monorepo, individual_repos, author, committer,
               logger_name):
    self.logger = logging.getLogger(logger_name)
    self.monorepo = monorepo
    self.individual_repos = individual_repos
    self.author = author
    self.committer = committer
    self.__initial_commit = None

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

  def _initial_commit(self, dest_branch_name):
    if not self.__initial_commit:
      head = self._maybe_head(dest_branch_name)
      if head:
        for commit in self.monorepo.iter_commits(dest_branch_name):
          if commit.message == INITIAL_COMMIT_MESSAGE:
            self.__initial_commit = commit
            # Not breaking here but instead going through the full
            # list of commits ensure that we are selecting the first
            # commit.  Indeed, `iter_commits` gives back the commits
            # in reverse chronological order.
        if not self.__initial_commit:
          raise Error("cannot find initial commit message")
      else:
        self.__initial_commit = self.monorepo.index.commit(
            INITIAL_COMMIT_MESSAGE,
            author = self.author,
            committer = self.committer)
    return self.__initial_commit

  def _remote_exists(self, name):
    try:
      self.monorepo.remote(name)
      return True
    except ValueError:
      return False

  def _maybe_head(self, branch_name):
    try:
      return self.monorepo.heads[branch_name]
    except IndexError:
      return None

  def create_remotes(self):
    self.logger.info("Create the individual repo remotes...")
    for individual_repo in self.individual_repos:
      self.logger.info("For {}".format(individual_repo.name))
      if self._remote_exists(individual_repo.name):
        self.monorepo.delete_remote(individual_repo.name)
      remote = self.monorepo.create_remote(individual_repo.name,
                                           individual_repo.location)

  def create_or_update_individual_repo_branches(self,
                                                dest_branch_name,
                                                fetch_depth = None):
    self.logger.info("Create or update individual repo branches...")
    to_update = []
    for individual_repo in self.individual_repos:
      repo_name = individual_repo.name
      branch_name = _individual_repo_branch_name(dest_branch_name, repo_name)
      self.logger.info("{}: pulling...".format(repo_name))
      repo_branch = self._maybe_head(branch_name)
      repo_branch_created = False
      if not repo_branch:
        repo_branch_created = True
        repo_branch = self.monorepo.create_head(
            branch_name, self._initial_commit(dest_branch_name))
      repo_branch.checkout()
      commit_before_pull = repo_branch.commit
      self.monorepo.remotes[repo_name].pull(
          individual_repo.branch,
          allow_unrelated_histories = repo_branch_created,
          depth = fetch_depth)
      commit_after_pull = repo_branch.commit
      if commit_before_pull == commit_after_pull:
        self.logger.info("{}: SKIP: up-to-date".format(repo_name))
        continue
      to_update.append(repo_name)
      self.logger.info(
          "{}: create destination directories...".format(repo_name))
      repo_branch.checkout()
      index = self.monorepo.index
      filenames = []
      for (key, value) in index.entries.items():
        filename = key[0]
        append = True
        for cur in self.individual_repos:
          if filename.startswith(cur.destination + "/"):
            append = False
            break
        if append:
          filenames.append(filename)
      dest_dirs_to_add = []
      for filename in filenames:
        dest_dir_rel = os.path.dirname(
            os.path.join(individual_repo.destination, filename))
        dest_dir_abs = os.path.join(self.monorepo.working_dir, dest_dir_rel)
        dest_dirs_to_add.append(dest_dir_abs)
        if not os.path.exists(dest_dir_abs):
          os.makedirs(dest_dir_abs)
      #index.add(dest_dirs_to_add)
      self.logger.info("{}: move files...".format(repo_name))
      for dest_dir_abs in set(dest_dirs_to_add):
        dest_dir_rel = os.path.relpath(dest_dir_abs, self.monorepo.working_dir)
        src_dir_rel = os.path.relpath(dest_dir_rel, individual_repo.destination)
        if src_dir_rel == ".":
          src_dir_rel = ""
        else:
          src_dir_rel += os.path.sep
        cur_filenames = []
        for filename in filenames:
          if filename.startswith(src_dir_rel.replace(os.path.sep, "/")):
            if "/" not in filename[len(src_dir_rel):]:
              cur_filenames.append(filename)
        cur_filenames.append(dest_dir_rel)
        index.move(cur_filenames)
      repo_branch.reference = index.commit(
          "Move files from repo {} to directory {}".format(
              repo_name, individual_repo.destination),
          author = self.author,
          committer = self.committer)
    return to_update

  def merge_individual_repo_branches(self, to_update, dest_branch_name):
    self.logger.info("Merge old repo branches...")
    dest_branch = self._maybe_head(dest_branch_name)
    if not dest_branch:
      dest_branch = self.monorepo.create_head(
          dest_branch_name, self._initial_commit(dest_branch_name))
    dest_branch.checkout()
    for repo_name in to_update:
      self.logger.info("{}: merge".format(repo_name))
      source_branch = self.monorepo.heads[_individual_repo_branch_name(
          dest_branch_name, repo_name)]
      merge_base = self.monorepo.merge_base(dest_branch, source_branch)
      index = self.monorepo.index
      index.merge_tree(source_branch, base = merge_base)
      next_commit = index.commit(
          "Merge repo {}".format(repo_name),
          parent_commits = (source_branch.commit, dest_branch.commit),
          author = self.author,
          committer = self.committer)
      dest_branch.commit = next_commit
    self.logger.info("Clean up working directory...")
    self.monorepo.head.reference = dest_branch
    for entry in os.listdir(self.monorepo.working_dir):
      if entry == ".git":
        continue
      path = os.path.join(self.monorepo.working_dir, entry)
      if os.path.isfile(path):
        os.remove(path)
      else:
        shutil.rmtree(path)
    self.monorepo.head.reset(index = True, working_tree = True)


def _default_repo_name(repo_location):
  name = repo_location[repo_location.rindex(os.sep) + 1:]
  if name.endswith('.git'):
    return name[:-len('.git')]
  return name


def _individual_repo_branch_name(dest_branch_name, repo_name):
  return 'individual_repos/{}/{}'.format(dest_branch_name, repo_name)
