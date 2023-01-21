#!/usr/bin/env python3

"""
Parse a TOML document and output data as tagged JSON in the format
expected by https://github.com/BurntSushi/toml-test
"""

import sys
import datetime
import json

import tomlkit


def tag(d):
    if isinstance(d, dict):
        return dict((k, tag(v)) for (k, v) in d.items())
    elif isinstance(d, list):
        return [tag(v) for v in d]
    elif isinstance(d, str):
        return {"type": "string", "value": d}
    elif isinstance(d, bool):
        return {"type": "bool", "value": str(d).lower()}
    elif isinstance(d, int):
        return {"type": "integer", "value": str(d)}
    elif isinstance(d, float):
        return {"type": "float", "value": str(d)}
    elif isinstance(d, datetime.datetime):
        if d.tzinfo is None:
            return {"type": "datetime-local", "value": d.isoformat()}
        else:
            return {"type": "datetime", "value": d.isoformat()}
    elif isinstance(d, datetime.date):
        return {"type": "date-local", "value": d.isoformat()}
    elif isinstance(d, datetime.time):
        return {"type": "time-local", "value": d.isoformat()}
    else:
        assert False, f"unsupported data type {type(d)}"


def main():

    if len(sys.argv) > 2:
        print("Usage:", sys.argv[0], "[filename.toml]", file=sys.stderr)
        sys.exit(1)

    if len(sys.argv) == 2:
        with open(sys.argv[1], "rb") as f:
            toml_bytes = f.read()
    else:
        toml_bytes = sys.stdin.buffer.read()

    toml_data = tomlkit.parse(toml_bytes)

    tagged_data = tag(toml_data.unwrap())

    json.dump(tagged_data, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()

