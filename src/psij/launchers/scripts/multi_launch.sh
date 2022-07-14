#!/bin/bash

source $(dirname "$0")/launcher_lib.sh

pre_launch

PIDS=""
_PSI_J_PROCESS_COUNT="$1"
shift
export _PSI_J_PROCESS_COUNT

for INDEX in $(seq 1 1 $_PSI_J_PROCESS_COUNT); do
    _PSI_J_PROCESS_INDEX_=$INDEX "$@" 1>>$_PSI_J_STDOUT 2>>$_PSI_J_STDERR  <$_PSI_J_STDIN &
    PIDS="$PIDS $!"
done

for PID in $PIDS ; do
    set +e
    wait $PID
    _PSI_J_EC=$?
    set -e
    if [ "$_PSI_J_EC" != "0" ]; then
        log "Pid $PID failed with $_PSI_J_EC"
        _PSI_J_FAILED_EC=$_PSI_J_EC
    fi
done

log "All completed"

post_launch

echo "_PSI_J_LAUNCHER_DONE"
exit $_PSI_J_FAILED_EC
