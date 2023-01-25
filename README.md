
This repository provides automated testing of several TOML parsers against the `toml-test` test suite.

[TOML](https://toml.io/) is a file format for configuration files. <br>
There are many implementations of TOML in various programming languages.

https://github.com/BurntSushi/toml-test is a test suite that can be used to verify the correctness of TOML parsers.

This repository is a half-hearted attempt to run automated testing of TOML parsers via GitHub Actions.
It currently does not work as nicely as I had hoped.

I don't expect to develop this much further. <br>
I will probably not fix issues and not accept pull requests.

### Random TOML documents

This repository contains a tool that generates random valid TOML 1.0.0 files:
[gen\_random\_toml.py](random_test/gen_random_toml.py) .

This tool can be used to test a TOML parser on randomly generated input, thus exposing bugs that are triggered by obscure combinations of valid TOML syntax.

It works and has found some actual parser bugs.
However, the generated random TOML files look very strange and are difficult to read.
When a generated file exposes a parser bug, it may still be difficult to figure out which _part_ of the file triggers the bug.

Running a parser on random input only makes sense for parsers that already pass the complete `toml-test` suite.
If the parser has known bugs, random input will probably just trigger those bugs again and again which is not very useful.

## Test results for TOML 1.0.0 compliance

The tables below were manually copied from workflow runs.
I have not found a good way to update these tables automatically.

### Testing latest release of parser

__Test date:__ 2023-01-25 <br>
__Test suite:__ https://github.com/BurntSushi/toml-test version v1.3.0-32-g261966e

| TOML parser | Version | # passed | # valid failed | # invalid failed | Result |
|-------------|---------|----------------|----------------------|------------------------|--------|
| Python tomllib | Python 3.11.1 | 413 | 0 | 0 | :heavy_check_mark: |
| https://github.com/BurntSushi/toml | v1.2.1 | 403 | 0 | 10 | :warning: |
| https://crates.io/crates/toml | v0.6.0 | 412 | 0 | 1 | :warning: |
| https://pypi.org/project/tomlkit/ | 0.11.6 | 402 | 1 | 10 | :x: |
| https://github.com/ToruNiina/toml11 | v3.7.1 | 411 | 1 | 1 | :x: |
| https://github.com/marzer/tomlplusplus | v3.2.0 | 411 | 2 | 0 | :x: |

### Testing latest commit to parser repository

__Test date:__ 2023-01-25 <br>
__Test suite:__ https://github.com/BurntSushi/toml-test version v1.3.0-32-g261966e

| TOML parser | Version | # passed | # valid failed | # invalid failed | Result |
|-------------|---------|----------------|----------------------|------------------------|--------|
| Python tomllib | Python 3.12.0a4 | 413 | 0 | 0 | :heavy_check_mark: |
| https://github.com/BurntSushi/toml | bd94408 | 403 | 0 | 10 | :warning: |
| https://github.com/toml-rs/toml | cc869e9 | 412 | 0 | 1 | :warning: |
| https://github.com/sdispater/tomlkit | 6512eaa | 402 | 1 | 10 | :x: |
| https://github.com/ToruNiina/toml11 | 22db720 | 412 | 1 | 0 | :x: |
| https://github.com/marzer/tomlplusplus | d8bb717 | 411 | 2 | 0 | :x: |

