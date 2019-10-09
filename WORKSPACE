workspace(name = "monorepo_tools")

load("@bazel_tools//tools/build_defs/repo:git.bzl", "git_repository")

# Sanity checks

git_repository(
    name = "bazel_skylib",
    remote = "https://github.com/bazelbuild/bazel-skylib",
    tag = "1.0.0",
)

load("@bazel_skylib//lib:versions.bzl", "versions")

versions.check("0.29.0")

git_repository(
    name = "rules_python",
    commit = "5aa465d5d91f1d9d90cac10624e3d2faf2057bd5",
    remote = "https://github.com/bazelbuild/rules_python.git",
)

# This call should always be present.
load("@rules_python//python:repositories.bzl", "py_repositories")

py_repositories()

# This one is only needed if you're using the packaging rules.
load("@rules_python//python:pip.bzl", "pip_repositories")

pip_repositories()

load("@rules_python//python:pip.bzl", "pip_import")

# This rule translates the specified requirements.txt into
# @my_deps//:requirements.bzl, which itself exposes a pip_install method.
pip_import(
    name = "py_deps",
    requirements = "//:requirements.txt",
)

# Load the pip_install symbol for my_deps, and create the dependencies'
# repositories.
load("@py_deps//:requirements.bzl", "pip_install")

pip_install()

# Linting
load("//internal:format.bzl", "format_repositories")

format_repositories()
