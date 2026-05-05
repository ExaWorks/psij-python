#!/bin/bash

set -e

echo "ABCD" > out.txt
echo "DEFG" > log.txt

echo "$PWD" >> ~/app.log
ls -al >> ~/app.log
