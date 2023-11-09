#!/bin/bash

# This script does the following:
# - does some sanity checks
# - updates RELEASE and src/psij/version.py
# - commits and pushes the version files
# - creates a release tag
# - builds packages
# - pushes said packages to PyPi
# - triggers github workflows to rebuild the web page (including documentation)

set -e

error() {
    echo $@
    exit 1
}

if [ "$1" == "" ]; then
    error "Missing required version argument"
else
    TARGET_VERSION="$1"
fi

# Ensure that we are on the main branch
CRT_BRANCH=`git rev-parse --abbrev-ref HEAD`

if [ "$CRT_BRANCH" != "main" ]; then
    error "Must be on the main branch to make a release."
fi

STATUS=`git status --untracked-files=no --porcelain`

# Ensure current dir is clean
if [ ! -z "$STATUS" ]; then
    error "Working directory is not clean. Please run this script on a clean checkout."
    echo
fi

# Make sure version in newer than other releases
TAGS=`git tag`
if echo "$TAGS" | grep "$TARGET_VERSION" 2>&1 >/dev/null; then
    error "Version $TARGET_VERSION is already tagged."
fi

LAST=`echo -e "$TAGS\n$TARGET_VERSION" | sed '/^\s*$/d' | sort -V | tail -n 1`
if [ "$LAST" != "$TARGET_VERSION" ]; then
    error "Version $TARGET_VERSION is lower than the latest tagged version ($LAST)."
fi

echo "This will tag and release psij-python to version $TARGET_VERSION."
echo -n "Type 'yes' if you want to continue: "
read REPLY

if [ "$REPLY" != "yes" ]; then
    error "Release canceled."
fi

# There are mutable operations from here on

echo "Creating release branch"
git checkout -b "release_$TARGET_VERSION"

# Update the two version files and push them
echo "Updating version and tagging..."

echo -n "$TARGET_VERSION" > RELEASE
cat <<EOF >src/psij/version.py
"""This module stores the current version of this library."""

# Do not change this file manually. It is updated automatically by the release script.
VERSION = '$TARGET_VERSION'
EOF

git commit -m "Updated version files to $TARGET_VERSION." RELEASE src/psij/version.py
git push --set-upstream origin release_$TARGET_VERSION

git tag -a "$TARGET_VERSION" -m "Tagging $TARGET_VERSION"
git push origin --tags

echo "Building packages..."
python3 setup.py sdist
python3 setup.py bdist_wheel

echo "Releasing PyPi package..."
twine upload dist/*

echo "Triggering web docs build..."
git commit --allow-empty -m "Trigger web build for $TARGET_VERSION"
git push

echo "All done!"