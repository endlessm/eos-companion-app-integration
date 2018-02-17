#!/bin/bash
GI_TYPELIB_PATH=/home/smspillaz/Source/eos-companion-app-integration:$GI_TYPELIB_PATH
LD_LIBRARY_PATH=/home/smspillaz/Source/eos-companion-app-integration/.libs:$LD_LIBRARY_PATH
PYTHONPATH=/home/smspillaz/Source/eos-companion-app-integration:$PYTHONPATH

pushd test
    python3 -m unittest $(basename ${1%.py})
popd

