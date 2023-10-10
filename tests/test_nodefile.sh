#!/bin/bash

set -e

EXPECTED_N_NODES="$1"
if [ "$EXPECTED_N_NODES" == "" ]; then
    echo "Missing expected node count argument"
    exit 3
fi

ACTUAL_N_NODES=`cat "$PSIJ_NODEFILE" | wc -l`

if [ "$EXPECTED_N_NODES" != "$ACTUAL_N_NODES" ]; then
    echo "Invalid node file. Expected $EXPECTED_N_NODES nodes, but got $ACTUAL_N_NODES."
    echo "Nodefile contents follows"
    cat "$PSIJ_NODEFILE"
    exit 2
fi
