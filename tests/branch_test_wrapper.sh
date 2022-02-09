#!/bin/bash

# This is here to allow a point of customization between branch tests
# and ci_runner.py, which is in the main branch.

export PYTHONPATH=`pwd`/tests/plugins1:`pwd`/tests/plugins2:$PYTHONPATH

"$@"