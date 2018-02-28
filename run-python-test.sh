#!/bin/bash -e
arguments=( "$@" )
last_argument="${arguments[-1]}"
head_arguments="${arguments[@]:0:$((${#arguments[@]} - 1))}"

pushd ${SOURCE_DIRECTORY}/test
    python3 -m unittest ${head_arguments} $(basename ${last_argument%.py})
popd
