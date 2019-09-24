load("@rules_python//python:defs.bzl", "py_binary", "py_library", "py_test")
load("@py_deps//:requirements.bzl", "requirement")

py_binary(
    name = "monorepo_tools",
    srcs = ["cli.py"],
    main = "cli.py",
    visibility = ["//visibility:public"],
    deps = [
        "//import_into",
    ],
)
