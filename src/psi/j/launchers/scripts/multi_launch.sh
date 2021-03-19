#!/bin/bash

PIDS=""
COUNT="$1"
shift
_PSI_J_PROCESS_COUNT_="$COUNT"
export _PSI_J_PROCESS_COUNT_

for INDEX in $(seq 1 1 $COUNT); do
    _PSI_J_PROCESS_INDEX_=$INDEX "$@" &
    PIDS="$PIDS $!"
done

for PID in $PIDS ; do
    wait $PID
    EC=$?
    if [ "$EC" != "0" ]; then
        FAILED_EC=$EC
    fi
done

exit $FAILED_EC