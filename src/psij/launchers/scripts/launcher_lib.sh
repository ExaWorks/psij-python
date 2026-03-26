set -e

# abspath Source - https://stackoverflow.com/a/23002317
# Posted by Alexander Klimetschek, modified by community. See post 'Timeline' for change history
# Retrieved 2026-03-26, License - CC BY-SA 3.0

function _psi_j_abspath() {
    if [[ $1 = /* ]]; then
        echo "$1"
    elif [[ $1 == */* ]]; then
        echo "$(cd "${1%/*}"; pwd)/${1##*/}"
    elif [ -n "$1" ]; then
        echo "$(pwd)/$1"
    fi
}

_PSI_J_JOB_ID="$1"
_PSI_J_LOG_FILE=$(_psi_j_abspath "$2")
_PSI_J_PRE_LAUNCH=$(_psi_j_abspath "$3")
_PSI_J_POST_LAUNCH=$(_psi_j_abspath "$4")
_PSI_J_STDIN=$(_psi_j_abspath "$5")
_PSI_J_STDOUT=$(_psi_j_abspath "$6")
_PSI_J_STDERR=$(_psi_j_abspath "$7")

shift 7

if [ "$_PSI_J_LOG_FILE" == "" ]; then
    _PSI_J_LOG_FILE="/dev/null"
fi

if [ "${BASH_VERSINFO[0]}" -gt 4 ] || { [ "${BASH_VERSINFO[0]}" -eq 4 ] && [ "${BASH_VERSINFO[1]}" -ge 2 ]; }; then
    ts() {
        local TZ=UTC
        while read LINE; do
            printf -v TS '%(%Y-%m-%d %H:%M:%S)T' -1
            echo "$TS $_PSI_J_JOB_ID $LINE"
        done
    }
else
    ts() {
        local TZ=UTC
        while read LINE; do
            TS=$(date '+%Y-%m-%d %H:%M:%S')
            echo "$TS $_PSI_J_JOB_ID $LINE"
        done
    }
fi

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
