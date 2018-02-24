#!/usr/bin/env python3
#
# Regenerate a flatpak manifest template from the pip dependencies file
# specified on the commandline.
#
#     Usage: regenerate_pip_flatpak_manifest.py GENERATOR_SCRIPT PIP
#                                               REQUIREMENTS
#                                               PIP_MANIFEST_PIECE
#
# You should use this whenever the pip requirements for the package
# change, since pip requirements are installed by flatpak itself
# during the build and testing phases. You should also check in the
# generated manifest into git, since it pins dependencies at certain versions.
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

import argparse
import json
import os
import subprocess
import sys
import tempfile


def generate_manifest_from_pip_requirements(generator_script,
                                            pip_requirements):
    '''Generate a manifest in memory from pip_requirements.

    The generator writes to disk, so we make it write to a temporary
    file 
    '''
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            with open(pip_requirements) as requirements_fileobj:
                requirements = [l.strip() for l in requirements_fileobj]
        except FileNotFoundError:
            return None

        # Empty file, manifest generator won't work in this case
        if not requirements:
            return None

        subprocess.run([
            'python3',
            os.path.abspath(generator_script),
            '--build-only',
        ] + requirements, cwd=tmpdir, check=True)

        # Take the only file generated in the tmpdir and treat it as
        # the manifest file (the manifest file has the same filename
        # as the first package specified)
        first_filename = os.listdir(tmpdir)[0]
        with open(os.path.join(tmpdir, first_filename)) as generated_fileobj:
            generated_pip_manifest = json.load(generated_fileobj)

        # Adjust name to be pip-requirements, this way we always know which
        # entry to replace in the manifest later
        generated_pip_manifest['name'] = 'pip-requirements'

        # Also adjust the build commands. The default is to just try
        # and build the very first module. This doesn't make much sense
        # in the context of reading the requirements file and also gets
        # things wrong, since it doesn't transitively explore dependencies,
        # which means that when we actually try to build the module we can't
        # due to the fact that PyPI's certificate is not installed in the
        # sandbox.
        pip_commands = [' '.join([
            'pip3',
            'install',
            '--no-index',
            '--find-links="file://${PWD}"',
            '--prefix=${FLATPAK_DEST}',
        ] + [req]) for req in requirements]
        generated_pip_manifest['build-commands'] = pip_commands

    return generated_pip_manifest


def main(args):
    '''Entry point.'''
    parser = argparse.ArgumentParser('Flatpak Manifest Template Regenerator')
    parser.add_argument('generator_script',
                        type=str,
                        metavar='GENERATOR_SCRIPT')
    parser.add_argument('pip_requirements',
                        type=str,
                        metavar='PIP_REQUIREMENTS')
    parser.add_argument('pip_manifest_piece',
                        type=str,
                        metavar='PIP_MANIFEST_PIECE')

    parsed_args = parser.parse_args(args)

    generated_piece = generate_manifest_from_pip_requirements(
        parsed_args.generator_script,
        parsed_args.pip_requirements
    )

    with open(parsed_args.pip_manifest_piece, 'w') as pip_manifest_fileobj:
        pip_manifest_fileobj.write(json.dumps(generated_piece,
                                              indent=4,
                                              sort_keys=True))


if __name__ == '__main__':
    main(sys.argv[1:])

