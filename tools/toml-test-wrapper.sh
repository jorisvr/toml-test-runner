#!/bin/bash

# Make "toml-test" binary executable.
# It might not be executable yet if it was downloaded as an artifact.
chmod a+x ./toml-test

# Make sure that the next command returns the exit status of "toml-test",
# not the exit status of "tee".
set -o pipefail

# Run "toml-test" with specified command line arguments.
# Copy data from stdout and append it to "logfile".
./toml-test "$@" | tee -a logfile

