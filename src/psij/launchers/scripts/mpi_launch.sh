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

filter_out() {
    sed -nE 's/^\[[^]]+\]<stdout>:(.*)/\1/p'
}

filter_err() {
    sed -nE 's/^\[[^]]+\]<stderr>:(.*)/\1/p'
}

filter_out_5() {
    sed -nE 's/^\[[^]]+\]<stdout>: (.*)/\1/p'
}

filter_err_5() {
    sed -nE 's/^\[[^]]+\]<stderr>: (.*)/\1/p'
}

set +e
if [ "$IS_OPENMPI_5" == "1" ]; then
    mpirun --oversubscribe --output TAG -n $_PSI_J_PROCESS_COUNT "$@" \
        1> >(filter_out_5 > $_PSI_J_STDOUT) 2> >(filter_err_5 > $_PSI_J_STDERR) <$_PSI_J_STDIN
elif [ "$IS_OPENMPI" == "1" ]; then
    mpirun --oversubscribe --tag-output -q -n $_PSI_J_PROCESS_COUNT "$@" \
        1> >(filter_out > "$_PSI_J_STDOUT") 2> >(filter_err > $_PSI_J_STDERR) <$_PSI_J_STDIN
else
    mpirun -n $_PSI_J_PROCESS_COUNT "$@" 1>$_PSI_J_STDOUT 2>$_PSI_J_STDERR <$_PSI_J_STDIN
fi
_PSI_J_EC=$?
set -e

log "Command done: $_PSI_J_EC"

post_launch

exit $_PSI_J_EC
