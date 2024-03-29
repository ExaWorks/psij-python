#!/bin/bash

xmodule() {
    case "$1" in
        load)
            export MODULE_TEST_LOADED="1"
            ;;
        is-loaded)
            if [ "$MODULE_TEST_LOADED" != "1" ]; then
                exit 2
            fi
            ;;
        *)
            exit 3
            ;;
     esac
}

export -f xmodule

xmodule load test
