#!/bin/bash

source $(dirname "$0")/launcher_lib.sh

pre_launch

set +e
"$@" 1>$_PSI_J_STDOUT 2>$_PSI_J_STDERR  <$_PSI_J_STDIN
_PSI_J_EC=$?
set -e
log "Command done: $_PSI_J_EC"

post_launch

echo "_PSI_J_LAUNCHER_DONE"
exit $_PSI_J_EC
