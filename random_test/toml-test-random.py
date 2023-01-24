#!/usr/bin/env python3

"""
Program to test a TOML parser on random valid TOML input.

This program runs a TOML parser on a randomly generated valid TOML file,
then checks that the parser returns a correct data structure.

The TOML parser is invoked as a separate program.
The TOML parser must output the parsed data in the same JSON format
as used by https://github.com/BurntSushi/toml-test
"""

import sys
import argparse
import datetime
import io
import json
import math
import random
import subprocess
from typing import Callable, NamedTuple

import gen_random_toml


class TestResult(NamedTuple):
    """Result of running a testcase."""
    success: bool
    reason: str
    seed: int
    toml_doc: str
    stdout_data: bytes
    stderr_data: bytes
    exit_status: int


class ParserRunner:
    """Helper class that invokes the TOML parser as an external program."""

    def __init__(self,
                 parser_command: str,
                 parser_options: list[str]
                 ) -> None:
        self.parser_command = parser_command
        self.parser_options = parser_options

    def run(self, toml_doc: str) -> tuple[bytes, bytes, int]:
        """Run the external TOML parser."""

        toml_bytes = toml_doc.encode("utf-8")

        args = [self.parser_command] + self.parser_options
        proc = subprocess.run(args, input=toml_bytes, capture_output=True)

        return (proc.stdout, proc.stderr, proc.returncode)


def _decode_tagged_bool(tag_value: str) -> bool:
    """Decode a tagged boolean value."""
    if tag_value == "true":
        return True
    elif tag_value == "false":
        return False
    else:
        raise ValueError(
            f"Invalid tagged boolean value {tag_value!a} in parser output")


def untag(tagged_data: object) -> object:
    """Decode tagged JSON data."""

    decoder_functions: dict[str, Callable[[str], object]] = {
        "string": str,
        "bool": _decode_tagged_bool,
        "integer": int,
        "float": float,
        "datetime": datetime.datetime.fromisoformat,
        "datetime-local": datetime.datetime.fromisoformat,
        "date-local": datetime.date.fromisoformat,
        "time-local": datetime.time.fromisoformat
    }

    if (isinstance(tagged_data, dict)
            and isinstance(tagged_data.get("type"), str)):

        tag_type = tagged_data.get("type")
        assert isinstance(tag_type, str)

        tag_value = tagged_data.get("value")
        if tag_value is None:
            raise ValueError(
                "Missing 'value' item in tagged value in parser output")
        if not isinstance(tag_value, str):
            raise ValueError(
                f"Tagged 'value' item must be encoded as string")

        if len(tagged_data) != 2:
            raise ValueError(
                "Unexpected items in tagged value in parser output"
                " (besides 'type' and 'value')")

        if tag_type not in decoder_functions:
            raise ValueError(
                f"Unexpected tagged type {tag_type!a} in parser output")

        try:
            return decoder_functions[tag_type](tag_value)
        except ValueError:
            raise ValueError(
                f"Invalid tagged {tag_type} format {tag_value!a}") from None

    elif isinstance(tagged_data, dict):
        return {key: untag(value) for (key, value) in tagged_data.items()}

    elif isinstance(tagged_data, list):
        return [untag(v) for v in tagged_data]

    else:
        raise ValueError(
            f"Unexpected type {type(tagged_data)} in parser output")


def check_result(
        parsed_data: object,
        gold_data: object,
        path: tuple[str, ...] = ()
        ) -> tuple[bool, str]:
    """Compare parser output to original data."""

    parsed_type = type(parsed_data)
    gold_type = type(gold_data)

    if isinstance(gold_data, list):

        if not isinstance(parsed_data, list):
            return (False, f"Key {path!a} has type {parsed_type}"
                           f" while expecting list")

        parsed_len = len(parsed_data)
        gold_len = len(gold_data)
        if parsed_len != gold_len:
            return (False, f"Key {path!a} is array of length {parsed_len}"
                           f" while expecting {gold_len}")

        for (i, (parsed_elem, gold_elem)) in enumerate(zip(parsed_data,
                                                           gold_data)):
            npath = path + (str(i), )
            (success, reason) = check_result(parsed_elem, gold_elem, npath)
            if not success:
                return (success, reason)

    elif isinstance(gold_data, dict):

        if not isinstance(parsed_data, dict):
            return (False, f"Key {path!a} has type {parsed_type}"
                           f" while expecting dict")

        for key in gold_data:
            if key not in parsed_data:
                npath = path + (key, )
                return (False, f"Key {npath!a} is missing from parsed data")

        for key in parsed_data:
            if key not in gold_data:
                npath = path + (key, )
                return (False, f"Unexpected key {npath!a} in parsed data")

        for key in gold_data:
            parsed_elem = parsed_data[key]
            gold_elem = gold_data[key]
            npath = path + (key, )
            (success, reason) = check_result(parsed_elem, gold_elem, npath)
            if not success:
                return (success, reason)

    else:

        if parsed_type is not gold_type:
            return (False, f"Key {path!a} has type {parsed_type}"
                           f" while expecting {gold_type}")

        if isinstance(gold_data, float) and math.isnan(gold_data):
            assert isinstance(parsed_data, float)
            if not math.isnan(parsed_data):
                return (False, f"Key {path!a} has value {parsed_data}"
                               f" while expecting nan")
        else:
            if parsed_data != gold_data:
                return (False, f"Key {path!a} has value {parsed_data!a}"
                               f" while expecting {gold_data!a}")
            if isinstance(gold_data, float):
                assert isinstance(parsed_data, float)
                parsed_sign = math.copysign(1, parsed_data)
                gold_sign = math.copysign(1, gold_data)
                if parsed_sign != gold_sign:
                    return (False, f"Key {path!a} has value {parsed_data}"
                                   f" while expecting {gold_data}")

    return (True, "")


def run_testcase(
        seed: int,
        runner: ParserRunner,
        normalize: bool
        ) -> TestResult:
    """Run one testcase."""

    rng = random.Random(seed)
    gen = gen_random_toml.TomlGenerator(rng, normalize)
    (toml_doc, toml_data) = gen.gen_toml()

    (stdout_data, stderr_data, exit_status) = runner.run(toml_doc)

    def make_result(success: bool, reason: str) -> TestResult:
        return TestResult(
            success=success,
            reason=reason,
            seed=seed,
            toml_doc=toml_doc,
            stdout_data=stdout_data,
            stderr_data=stderr_data,
            exit_status=exit_status)

    if exit_status != 0:
        return make_result(
            success=False,
            reason=f"Parser returned exit status {exit_status}")

    if not stdout_data:
        return make_result(
            success=False,
            reason="Parser returned empty output on stdout")

    try:
        json_data = json.loads(stdout_data)
    except ValueError as exc:
        return make_result(
            success=False,
            reason=f"Parser returned invalid JSON data ({exc})")

    try:
        parsed_data = untag(json_data)
    except ValueError as exc:
        return make_result(
            success=False,
            reason=f"Parser returned invalid tagged JSON ({exc})")

    (success, reason) = check_result(parsed_data, toml_data)
    return make_result(success, reason)


def show_parser_output(source: str, data: bytes) -> None:
    """Show parser output."""
    print(f"    parser {source}:")
    s = data.decode("utf-8", errors="replace")
    s = s.replace("\a", "")
    s = s.replace("\b", "")
    s = s.replace("\t", " ")
    for line in s.splitlines():
        print(7 * " ", line)


def dump_data(result: TestResult) -> None:
    """Write failed testcase to files."""

    name = f"failed_{result.seed}"

    with open(name + ".toml", "wb") as f:
        f.write(result.toml_doc.encode("utf-8"))

    if result.stderr_data:
        with open(name + ".err", "wb") as f:
            f.write(result.stderr_data)

    with open(name + ".out", "wb") as f:
        f.write(result.stdout_data)


def run_tests(
        parser_command: str,
        parser_options: list[str],
        num_testcases: int,
        start_seed: int,
        dumpfail: bool,
        normalize: bool,
        verbose: bool,
        quiet: bool
        ) -> int:
    """Run testcases and report results."""

    if not quiet:
        print("Running {} testcases, random seed from {} to {}".format(
            num_testcases, start_seed, start_seed + num_testcases - 1))
        print("Invoking TOML parser as '{}'".format(
            " ".join([parser_command] + parser_options)))
        sys.stdout.flush()

    runner = ParserRunner(parser_command, parser_options)

    num_pass = 0
    num_fail = 0

    for i in range(num_testcases):
        seed = start_seed + i
        result = run_testcase(seed=seed, runner=runner, normalize=normalize)

        if result.success:
            num_pass += 1
        else:
            num_fail += 1

        if not result.success:
            if (not verbose) and (not quiet):
                print()
            print("FAIL", f"seed={seed}", ":", result.reason)
            if result.stderr_data:
                show_parser_output("stderr", result.stderr_data)
            elif result.exit_status != 0 and result.stdout_data:
                show_parser_output("stdout", result.stdout_data)
            if dumpfail:
                dump_data(result)

        elif verbose:
            print("PASS", f"seed={seed}")
            sys.stdout.flush()

        elif not quiet:
            # Show progress.
            sys.stdout.write(".")
            sys.stdout.flush()

    if (not verbose) and (not quiet):
        print()

    print("Test summary: {} passed, {} failed".format(num_pass, num_fail))

    if num_fail == 0:
        return 0
    else:
        return 1


def main() -> None:
    """Main program function."""

    parser = argparse.ArgumentParser(
        description="""
Program to test a TOML parser on random valid TOML input.

The TOML parser is invoked as a separate program. The parser should
read TOML input from stdin and write parsed output to stdout in the
same JSON format as used by the "toml-test" suite.

See https://github.com/BurntSushi/toml-test#json-encoding for a
description of the JSON format.""",
        formatter_class=argparse.RawDescriptionHelpFormatter)

    parser.add_argument(
        "parser_command", action="store", type=str,
        help="program to run as TOML parser")
    parser.add_argument(
        "parser_options", action="store", type=str, nargs="*",
        help="optional parameters to pass to the parser")
    parser.add_argument(
        "-n", "--n", action="store", type=int, default=1,
        help="number of testcases to run (default 1)")
    parser.add_argument(
        "--seed", action="store", type=int, default=1,
        help="initial random seed (default 1)")
    parser.add_argument(
        "--dumpfail", action="store_true",
        help='dump failed testcases to files "failed_{seed}.toml/.out"')
    parser.add_argument(
        "--no-normalize", action="store_true",
        help="disable newline normalization in multi-line strings")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="list all testcases, including passed tests")
    parser.add_argument(
        "--quiet", action="store_true",
        help="do not show progress")

    args = parser.parse_args()

    if args.n < 1:
        print("ERROR: Invalid number of testcases", file=sys.stderr)
        sys.exit(1)

    if args.seed < 0:
        print("ERROR: Invalid random seed", file=sys.stderr)
        sys.exit(1)

    status = run_tests(
        parser_command=args.parser_command,
        parser_options=args.parser_options,
        num_testcases=args.n,
        start_seed=args.seed,
        dumpfail=args.dumpfail,
        normalize=(not args.no_normalize),
        verbose=args.verbose,
        quiet=args.quiet)
    sys.exit(status)


if __name__ == "__main__":
    main()
