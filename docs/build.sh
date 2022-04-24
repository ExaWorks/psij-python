#!/bin/bash

set -e

if [ ! -f docs/build.sh ]; then
	echo "This script must be run from the root of the repository."
	exit 1
fi

if [ "$1" != "--quick" ]; then
	pip install -r requirements-docs.txt
	make docs
	touch docs/build/.nojekyll
fi
