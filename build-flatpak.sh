#!/bin/bash
set -e
set -x
rm -rf files var metadata export build

BRANCH=${BRANCH:-master}
GIT_CLONE_BRANCH=${GIT_CLONE_BRANCH:-HEAD}

sed \
  -e "s|@BRANCH@|${BRANCH}|g" \
  -e "s|@GIT_CLONE_BRANCH@|${GIT_CLONE_BRANCH}|g" \
  com.endlessm.CompanionAppService.json.in \
  > com.endlessm.CompanionAppService.json

flatpak-builder build com.endlessm.CompanionAppService.json
flatpak build-export repo build ${BRANCH}
flatpak build-bundle repo com.endlessm.CompanionAppService.flatpak com.endlessm.CompanionAppService
