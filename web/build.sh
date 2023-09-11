#!/bin/bash

set -e

if [ ! -f web/build.sh ]; then
	echo "This script must be run from the root of the repository."
	exit 1
fi

if [ "$1" != "--quick" ]; then
	mkdir -p web-build

	pip install -r requirements-docs.txt

	if [ "$1" == "--dev" ]; then
	    make web-docs-dev
	else
		make web-docs
	fi

	mkdir -p web-build/docs
	echo "Copying docs..."
	cp -r docs/.web-build/. web-build/docs/
fi


cp -r web/_layouts/ web-build/
cp -r web/_includes/ web-build/
cp -r web/images/ web-build/

echo -n "var DOC_VERSIONS_RAW = [" >web-build/versions.js
for V in `ls web-build/docs/v`; do
	echo "Patching version $V"
	cp -r web/docs/_static web-build/docs/v/$V/

	echo "\"$V\", " >>web-build/versions.js
done
echo "]" >>web-build/versions.js

for F in `ls web/*`; do
	if [ -f "$F" ]; then
		cp "$F" web-build/
	fi
done

cp web/docs/index.html web-build/docs/

rm -f web-build/*.sh
rm -f web-build/README
