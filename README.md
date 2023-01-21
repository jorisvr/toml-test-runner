
This repository provides automated testing of several TOML parsers against the `toml-test` test suite.

[TOML](https://toml.io/) is a file format for configuration files. <br>
There are many implementations of TOML in various programming languages.

https://github.com/BurntSushi/toml-test is a test suite that can be used to verify the correctness of TOML parsers.

This repository is a half-hearted attempt to run automated testing of TOML parsers via GitHub Actions.
It currently does not work as nicely as I had hoped.

I don't expect to develop this much further. <br>
I will probably not fix issues and not accept pull requests.

## Test results for TOML 1.0.0 compliance

The tables below were manually copied from workflow runs.
I have not found a good way to update these tables automatically.

### Testing latest release of parser

__Test date:__ 2023-01-21 <br>
__Test suite:__ https://github.com/BurntSushi/toml-test version v1.3.0-32-g261966e

| TOML parser | Version | # passed | # valid failed | # invalid failed | Result |
|-------------|---------|----------------|----------------------|------------------------|--------|
| Python tomllib | Python 3.11.1 | 413 | 0 | 0 | :heavy_check_mark: |
| https://github.com/BurntSushi/toml | v1.2.1 | 403 | 0 | 10 | :warning: |
| https://crates.io/crates/toml | v0.5.11 | 407 | 2 | 4 | :x: |
| https://pypi.org/project/tomlkit/ | 0.11.6 | 402 | 1 | 10 | :x: |
| https://github.com/ToruNiina/toml11 | v3.7.1 | 411 | 1 | 1 | :x: |
| https://github.com/marzer/tomlplusplus | v3.2.0 | 411 | 2 | 0 | :x: |

### Testing latest commit to parser repository

__Test date:__ 2023-01-21 <br>
__Test suite:__ https://github.com/BurntSushi/toml-test version v1.3.0-32-g261966e

| TOML parser | Version | # passed | # valid failed | # invalid failed | Result |
|-------------|---------|----------------|----------------------|------------------------|--------|
| https://github.com/BurntSushi/toml | 7edfd73 | 403 | 0 | 10 | :warning: |
| https://github.com/toml-rs/toml | fe118f5 | 412 | 0 | 1 | :warning: |
| https://github.com/sdispater/tomlkit | 6512eaa | 402 | 1 | 10 | :x: |
| https://github.com/ToruNiina/toml11 | 22db720 | 412 | 1 | 0 | :x: |
| https://github.com/marzer/tomlplusplus | 698285d | 411 | 2 | 0 | :x: |

