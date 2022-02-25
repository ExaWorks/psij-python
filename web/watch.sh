#!/bin/bash

set -e

if [ ! -f web/build.sh ]; then
	echo "This script must be run from the root of the repository."
	exit 1
fi

web/build.sh

while true; do
	inotifywait -e modify,create,delete -r web/ && web/build.sh --quick
done