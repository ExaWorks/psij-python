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
        TZ=UTC TS=`date '+%Y-%m-%d %H:%M:%S'`
        echo "$TS $_PSI_J_JOB_ID $LINE"
    done
}

log() {
    echo "$@" >&3
}
exec 3> >(ts >> "$_PSI_J_LOG_FILE")

log "Launcher: $0"
log "Pre-launch: \"$_PSI_J_PRE_LAUNCH\""
log "Post-launch: \"$_PSI_J_POST_LAUNCH\""

pre_launch() {
    if [ "$_PSI_J_PRE_LAUNCH" != "" ]; then
        log "Running pre-launch"
        source "$_PSI_J_PRE_LAUNCH"
    fi
}

post_launch() {
    if [ "$_PSI_J_POST_LAUNCH" != "" ]; then
        log "Running post-launch"
        source "$_PSI_J_POST_LAUNCH"
    fi
}
