"""Command-Line Interface"""
import re
import os
from git import Repo, SymbolicReference
import gitdb
import shutil
import logging
import argparse
import sys
from monorepo_tools.import_into import import_into_monorepo, IndividualRepo

VERSION = '0.0.1'


def local_monorepo(monorepo_local_path):
  if os.path.exists(monorepo_local_path):
    return Repo(monorepo_local_path)

  print("Monorepo does not exist. Create it from scratch...")
  return Repo.init(monorepo_local_path, bare = False)


def load_source(name, path):
  """Loads a python module from its name (e.g., `foo.bar`) and its
  path (e.g., `/foo/bar.py`).

  Provides a compatibility layer between Python 3 and Python 2.7
  """
  if sys.version_info >= (3, 0):
    import importlib.machinery
    mod_loader = importlib.machinery.SourceFileLoader(name, path)
    return mod_loader.load_module()

  import imp
  return imp.load_source(name, path)


def main():
  """Parses the command-line arguments."""
  parser = argparse.ArgumentParser(
      "monorepo_tools", description = 'Monorepo tools {}'.format(VERSION))
  subparsers = parser.add_subparsers(dest = 'subcommand')

  import_parser = subparsers.add_parser(
      'import', description = 'Import individual repos into a monorepo')
  import_parser.add_argument(
      '--individual_repos',
      required = True,
      help = (
          'Path to python module that exports one function, individual_repos, '
          + 'that takes the destination branch name as an argument'))
  import_parser.add_argument(
      '--dest_branch',
      required = True,
      help = 'The destination branch to import into')
  import_parser.add_argument(
      '--monorepo_path',
      required = True,
      help =
      'The local path to the monorepo (it is created if it does not exist)')

  options = parser.parse_args()

  if options.subcommand == 'import':
    mod = load_source('individual_repos', options.individual_repos)
    repos = mod.individual_repos(options.dest_branch)
    monorepo = local_monorepo(options.monorepo_path)
    import_into_monorepo(monorepo, repos, options.dest_branch)
  else:
    raise Exception("unexpected subcommand {}".format(options.subcommand))


if __name__ == "__main__":
  main()
