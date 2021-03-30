#define _HASH_ #
#define _BIN_BASH_ #!/bin/bash

set -e

_PSI_J_JOB_ID="$1"
_PSI_J_LOG_FILE="$2"

if [ "$_PSI_J_LOG_FILE" == "" ]; then
    _PSI_J_LOG_FILE="/dev/null"
fi

ts() {
    while read LINE; do
        printf -v TS "%(%F %T%z)T" -1
        echo "$TS $_PSI_J_JOB_ID $LINE"
    done
}

// Save out and err to FDs 3 and 4, and redirect out and err to log file
exec 3>&1 4>&2 > >(ts >> "$_PSI_J_LOG_FILE") 2>&1

_PSI_J_PRE_LAUNCH="$3"
_PSI_J_POST_LAUNCH="$4"
shift 4

echo "Pre-launch: \"$_PSI_J_PRE_LAUNCH\""
echo "Post-launch: \"$_PSI_J_POST_LAUNCH\""

pre_launch() {
    if [ "$_PSI_J_PRE_LAUNCH_" != "" ]; then
        echo "Running pre-launch"
        source "$_PSI_J_PRE_LAUNCH_"
    fi
}

post_launch() {
    if [ "$_PSI_J_POST_LAUNCH_" != "" ]; then
        echo "Running post-launch"
        source "$_PSI_J_POST_LAUNCH_"
    fi
}
