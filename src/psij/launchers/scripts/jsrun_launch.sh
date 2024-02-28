#!/bin/bash

source $(dirname "$0")/launcher_lib.sh

_PSI_J_PROCESS_COUNT="$1"
shift

pre_launch

set +e
jsrun -p $_PSI_J_PROCESS_COUNT --np 1 "$@" 1>$_PSI_J_STDOUT 2>$_PSI_J_STDERR <$_PSI_J_STDIN
_PSI_J_EC=$?
set -e

log "Command done: $_PSI_J_EC"

post_launch

exit $_PSI_J_EC
