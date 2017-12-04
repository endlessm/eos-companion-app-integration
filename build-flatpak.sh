#!/bin/bash
set -x
rm -rf files var metadata export build

RUNTIME_VERSION=${RUNTIME_VERSION:-2}
BRANCH=${BRANCH:-master}
GIT_REPO_URL=${GIT_REPO_URL:-${PWD}}

sed \
  com.endlessm.CompanionAppService.json.in \
  -e "s|@RUNTIME_VERSION@|${RUNTIME_VERSION}|g;s|@BRANCH@|${BRANCH}|g;s|@GIT_REPO_URL@|${GIT_REPO_URL}|g" > com.endlessm.CompanionAppService.json

flatpak-builder build com.endlessm.CompanionAppService.json
flatpak build-export repo build ${BRANCH}
flatpak build-bundle repo com.endlessm.CompanionAppService.flatpak com.endlessm.CompanionAppService
