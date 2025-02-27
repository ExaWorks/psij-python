#!/bin/bash

source $(dirname "$0")/launcher_lib.sh

_PSI_J_PROCESS_COUNT="$1"
shift

IS_OPENMPI=0
IS_OPENMPI_5=0
if mpirun -version | grep "(Open MPI) 5" >/dev/null 2>&1; then
    IS_OPENMPI_5=1
elif mpirun -version | grep "Open MPI" >/dev/null 2>&1; then
    IS_OPENMPI=1
fi

pre_launch

# We need to use a marker for when actual output starts because some mpi deployments add
# banners at the beginning of the mpirun output. There are two seemingly reasonable
# ways of extracting the output: --tag-output and --xml. Unfortunately, --tag-output is broken
# and occasionally mashes two lines together in the form "part1<TAG>:part2" instead of
# "<TAG>:part1part2". So we really only have XML
process_line() {
    LINE="$1"
    if [[ "$LINE" =~ \<stdout ]]; then
        FILE="$_PSI_J_STDOUT"
    elif [[ "$LINE" =~ \<stderr ]]; then
        FILE="$_PSI_J_STDERR"
    else
        return
    fi
    # We first remove </mpirun>, which can be found after </stdout>.
    # The rest is about converting &#nnnn; entities to something that we can print with other
    # POSIX tools. The %c specified does not work properly for the bash printf, since it requires
    # an integer as input, but we can only supply strings. We can either use awk's printf or
    #
    P1=$(echo $LINE | sed -nE 's/<\/?mpirun>//g; s/&#0*/\&#/g; s/<std...[^>]*>([^<]*)<\/std...>/\1/g p')
    FMT=$(echo "$P1" | sed 's/\\/\\\\/g;s/%/%%/g;s/&#[0-9]*;/%c/g;s/&gt;/>/g;s/&lt;/</g;s/&amp;/\&/g;s/"/\"/g')
    NUMS=$(echo "$P1" | grep -o '&#[0-9]*;' | tr '&#;' '  ,' )
    awk "BEGIN {printf \"$FMT%s\", $NUMS \"\"}" >>"$FILE"
}

filter_out() {
    while IFS= read LINE; do
        process_line "$LINE"
    done
    # If the last line does not end in a newline, read will exit with a non-zero code but still
    # set the variable to the contents of that line. Not sure how portable this is.
    if [ "$LINE" != "" ]; then
        process_line "$LINE"
    fi
}

# truncate output since we append in the functions above
> $_PSI_J_STDOUT
> $_PSI_J_STDERR

set +e
if [ "$IS_OPENMPI_5" == "1" ]; then
    mpirun --oversubscribe --output XML -n $_PSI_J_PROCESS_COUNT "$@" \
      1> >(filter_out) <$_PSI_J_STDIN
elif [ "$IS_OPENMPI" == "1" ]; then
    mpirun --oversubscribe -q -xml -n $_PSI_J_PROCESS_COUNT "$@" \
      1> >(filter_out) <$_PSI_J_STDIN
else
    mpirun -n $_PSI_J_PROCESS_COUNT "$@" 1>$_PSI_J_STDOUT 2>$_PSI_J_STDERR <$_PSI_J_STDIN
fi
_PSI_J_EC=$?
set -e

log "Command done: $_PSI_J_EC"

post_launch

echo "_PSI_J_LAUNCHER_DONE"
exit $_PSI_J_EC
