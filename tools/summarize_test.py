#!/usr/bin/env python3

"""
Read log files from test jobs and generate a summary of test results.
Write summary to stdout as a markdown snippet.
"""

import sys
import re


def analyze_logfile(file_name):

    info = {}
    num_valid_failed = 0
    num_invalid_failed = 0

    with open(file_name, "r", encoding="utf-8", errors="replace") as f:
        for line in f:

            m = re.match(r"^Project: (.*)$", line)
            if m:
                info["project"] = m.group(1)

            m = re.match(r"^Version: (.*)$", line)
            if m:
                info["version"] = m.group(1)

            m = re.match(r"^(?:\s|\u001b.*m)*FAIL(?:\s|\u001b.*m)*(valid|invalid)/", line)
            if m:
                test_group = m.group(1)
                if test_group == "valid":
                    num_valid_failed += 1
                if test_group == "invalid":
                    num_invalid_failed += 1

            m = re.match(r"^toml-test.*:\s+([0-9]+) passed,\s+([0-9]+) failed", line)
            if m:
                info["num_passed"] = int(m.group(1))
                info["num_failed"] = int(m.group(2))

    info["num_valid_failed"] = num_valid_failed
    info["num_invalid_failed"] = num_invalid_failed

    return info


def write_summary(log_info):

    print("| TOML parser | Version | # passed | # valid failed | # invalid failed | Result |")
    print("|-------------|---------|----------------|----------------------|------------------------|--------|")

    for test_info in log_info:
        write_test_summary(test_info)


def write_test_summary(test_info):

    if "project" not in test_info:
        return
    if "version" not in test_info:
        return
    if "num_passed" not in test_info:
        return
    if "num_failed" not in test_info:
        return

    num_passed = test_info["num_passed"]
    num_failed = test_info["num_failed"]
    num_valid_failed = test_info["num_valid_failed"]
    num_invalid_failed = test_info["num_invalid_failed"]

    if num_failed == 0:
        mark = ":heavy_check_mark:"
    elif num_valid_failed == 0:
        mark = ":warning:"
    else:
        mark = ":x:"

    columns = [
        test_info["project"],
        test_info["version"],
        str(num_passed),
        str(num_valid_failed),
        str(num_invalid_failed),
        mark
    ]

    print("| " + " | ".join(columns) + " |")


def main():

    if len(sys.argv) <= 1:
        print("__Error: No test log files found__")
        sys.exit(1)

    log_files = sys.argv[1:]
    log_info = [analyze_logfile(file_name) for file_name in log_files]

    write_summary(log_info)


if __name__ == "__main__":
    main()

