#!/bin/bash

set -e

_PSI_J_JOB_ID="$1"
_PSI_J_LOG_FILE="$2"
_PSI_J_PRE_LAUNCH="$3"
_PSI_J_POST_LAUNCH="$4"
_PSI_J_STDIN="$5"
_PSI_J_STDOUT="$6"
_PSI_J_STDERR="$7"

shift 7

if [ "$_PSI_J_LOG_FILE" == "" ]; then
    _PSI_J_LOG_FILE="/dev/null"
fi

ts() {
    while read LINE; do
        printf -v TS "%(%F %T%z)T" -1
        echo "$TS $_PSI_J_JOB_ID $LINE"
    done
}

log() {
    echo "$@" >&3
}
exec 3> >(ts >> "$_PSI_J_LOG_FILE")

log "Pre-launch: \"$_PSI_J_PRE_LAUNCH\""
log "Post-launch: \"$_PSI_J_POST_LAUNCH\""

pre_launch() {
    if [ "$_PSI_J_PRE_LAUNCH_" != "" ]; then
        log "Running pre-launch"
        exec 4>&1 5>&2
        source "$_PSI_J_PRE_LAUNCH_"
        exec 1>&4 2>&5 4>&- 5>&-
    fi
}

post_launch() {
    if [ "$_PSI_J_POST_LAUNCH_" != "" ]; then
        log "Running post-launch"
        exec 4>&1 5>&2
        source "$_PSI_J_POST_LAUNCH_"
        exec 1>&4 2>&5 4>&- 5>&-
    fi
}
