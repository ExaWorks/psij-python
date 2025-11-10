#!/bin/bash

source $(dirname "$0")/launcher_lib.sh

pre_launch

log "Args: $@"

PIDS=""
_PSI_J_PROCESS_COUNT="$1"
_PSI_J_NODE_COUNT="$2"
_PSI_J_PPN="$3"
shift 3
export _PSI_J_PROCESS_COUNT
export _PSI_J_NODE_COUNT
export _PSI_J_PPN

EXECUTABLE="$1"
shift
if [ "$EXECUTABLE" == "/bin/hostname" ]; then
    EXECUTABLE=$(dirname "$0")/hostname
fi

log "Running stuff"
log "STDOUT: $_PSI_J_STDOUT"
log "STDERR: $_PSI_J_STDERR"

for NODE in $(seq 1 1 $_PSI_J_NODE_COUNT); do
    log "Node: $NODE"
    for NODE_PROC in $(seq 1 1 $_PSI_J_PPN); do
        log "Node proc: $NODE_PROC"
        INDEX=$(($NODE * $_PSI_J_PPN + $NODE_PROC))
        log "Index: $INDEX"
        _PSI_J_NODE_INDEX_=$NODE _PSI_J_PROCESS_INDEX_=$INDEX "$EXECUTABLE" "$@" 1>>$_PSI_J_STDOUT 2>>$_PSI_J_STDERR  <$_PSI_J_STDIN &
        PIDS="$PIDS $!"
    done
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

exit $_PSI_J_FAILED_EC
