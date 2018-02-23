#!/bin/bash
#
# test_data/scripts/generate_content_shard.sh
#
# Usage: generate_gresource_file.sh GRESOURCE_FILE
#
# Generate a gresource file and from app files in the current directory.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
# All rights reserved.

function usage() {
    echo "generate_gresource_file.sh RUNTIME_VERSION SOURCES_DIRECTORY GRESOURCE_FILE"
}

RUNTIME_VERSION=$1
SOURCES_DIRECTORY=$2
GRESOURCE_FILE=$3
GRESOURCE_MANIFEST_DIR=$(mktemp -d)
GRESOURCE_MANIFEST_FILE="${GRESOURCE_MANIFEST_DIR}/gresources.xml"

printf "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n<gresources><gresource prefix=\"/app\"><file>overrides.scss</file></gresource></gresources>" > "${GRESOURCE_MANIFEST_FILE}"

flatpak run \
	"--filesystem=$(readlink -f ${SOURCES_DIRECTORY})" \
	"--filesystem=$(readlink -f $(dirname ${GRESOURCE_FILE}))" \
	"--filesystem=$(readlink -f $(dirname ${GRESOURCE_MANIFEST_FILE}))" \
	"--command=glib-compile-resources" \
	"com.endlessm.apps.Sdk//${RUNTIME_VERSION}" \
	"--target=${GRESOURCE_FILE}" \
	"--sourcedir=${SOURCES_DIRECTORY}" \
	"${GRESOURCE_MANIFEST_FILE}"

