# Implementation of the "import" command.

load("@rules_python//python:defs.bzl", "py_library", "py_test")
load("@py_deps//:requirements.bzl", "requirement")

py_library(
    name = "import_into",
    srcs = [
        "__init__.py",
        "import_into.py",
    ],
    visibility = ["//visibility:public"],
    deps = [
        requirement("GitPython"),
        requirement("gitdb"),
        requirement("smmap"),
        "//common",
    ],
)

py_test(
    name = "import_into_test",
    srcs = [
        "import_into_test.py",
        "testutils.py",
    ],
    deps = [
        ":import_into",
        requirement("attrs"),
    ],
)

py_test(
    name = "e2e_test",
    srcs = [
        "e2e_test.py",
        "single_commit.py",
    ],
    data = [
        ":individual_repos.py",
        "//:monorepo_tools",
    ],
    tags = ["e2e"],
    deps = [
        ":import_into",
        requirement("attrs"),
        "@rules_python//python/runfiles",
    ],
)
