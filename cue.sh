#!/bin/bash

unset PYTHONPATH

REALPATH=$(readlink -f "$0")
cd $(dirname $REALPATH)

poetry run python cue.py "$@"
