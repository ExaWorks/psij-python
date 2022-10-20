#!/bin/bash
set -euf -o pipefail

create_tag () {

    if [ -z ${1+x} ]; then
        VERSION="unknown"
    else
        VERSION=$1
    fi

    PSIJ_VERSION=$(PYTHONPATH=./src python3 -c "import psij; print(psij.__version__)" 2>/dev/null)

    if [[ "$PSIJ_VERSION" == "$VERSION" ]]; then
        echo "Version requested matches package version: $VERSION"
    else
        echo "[ERROR] Version mismatch. User request: '$VERSION' while package version is: '$PSIJ_VERSION'"
        exit 1
    fi

    RELEASE=$(cat RELEASE)

    if [[ "$RELEASE" == "$VERSION" ]]; then
        echo "Release also matches package version: $VERSION"
    else
        echo "[ERROR] Version mismatch. User request: '$VERSION' while RELEASE is: '$RELEASE'"
    fi

    echo "Creating tag"
    git tag -a "$VERSION" -m "Psij $VERSION"

    echo "Pushing tag"
    git push origin --tags

}

package() {

    rm -f dist/*

    echo "======================================================================="
    echo "Starting clean builds"
    echo "======================================================================="
    python3 setup.py sdist
    python3 setup.py bdist_wheel

    echo "======================================================================="
    echo "Done with builds"
    echo "======================================================================="


}

release () {
    echo "======================================================================="
    echo "Push to PyPi. This will require your username and password"
    echo "======================================================================="
    twine upload dist/*
}

"$@"
