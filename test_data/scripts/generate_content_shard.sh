#!/bin/bash
#
# test_data/scripts/generate_content_shard.sh
#
# Usage: generate_content_shard.sh RUNTIME_VERSION DB_JSON CONTENT_SHARD
#
# Generate a content shard from some db.json file using
# the given runtime version. The relevant Flatpak SDK must be installed.
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
    echo "generate_content_shard.sh DB_JSON CONTENT_SHARD"
}

DB_JSON=$1
CONTENT_SHARD=$2

flatpak run \
	"--filesystem=$(readlink -f $(dirname ${DB_JSON}))" \
	"--filesystem=$(readlink -f $(dirname ${CONTENT_SHARD}))" \
	"--devel" \
	"--command=/app/bin/basin" \
	"com.endlessm.CompanionAppService" \
	"${DB_JSON}" \
	"${CONTENT_SHARD}"

