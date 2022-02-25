#!/bin/bash

set -e

if [ ! -f web/build.sh ]; then
	echo "This script must be run from the root of the repository."
	exit 1
fi

if [ "$1" != "--quick" ]; then
	mkdir -p web-build

	pip install -r requirements-docs.txt
	make web-docs

	mkdir -p web-build/docs
	cp -r docs/.web-build/. web-build/docs/
fi

cp -r web/. web-build/
cp web/*.css web-build/docs/_static/

rm -f web-build/*.sh
