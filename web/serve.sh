#!/bin/bash

if [ ! -f web/build.sh ]; then
	echo "This script must be run from the root of the repository."
	exit 1
fi

cd web-build
bundle exec jekyll serve
cd ..