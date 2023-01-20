#!/usr/bin/env python3

"""
Print the tag name that belongs to the latest release of a GitHub project.
"""

import sys
import json
import urllib.request


def get_latest_release(repo):

    url = "https://api.github.com/repos/" + repo + "/releases/latest"
    headers = {"accept": "application/vnd.github+json"}

    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        data = resp.read()

    info = json.loads(data)
    return info["tag_name"]


def main():
 
    if (len(sys.argv) != 2
            or sys.argv[1].lower().startswith("https:")
            or sys.argv[1].lower().startswith("http:")):
        print("Usage:", sys.argv[0], "owner/repo", file=sys.stderr)
        sys.exit(1)

    print(get_latest_release(sys.argv[1]))


if __name__ == "__main__":
    main()

