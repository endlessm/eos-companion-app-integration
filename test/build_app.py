# /test/build_app.py
#
# Helper functions to build flatpak apps for testing
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
'''Helper functions to build flatpak apps for tests.'''

import json
import hashlib
import os
import shutil

from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime
from subprocess import (
    PIPE,
    run as subprocess_run
)
from tempfile import NamedTemporaryFile, mkdtemp
from xml.etree import cElementTree as ET

import gi

gi.require_version('EosShard', '0')
gi.require_version('Flatpak', '1.0')

from gi.repository import EosShard, Flatpak, GLib


def run(*args, **kwargs):
    '''Wrapper for run, to show the commands being run.'''
    show_command = kwargs.get('show_command', None)
    if show_command is not None:
        if show_command:
            print(' '.join(args[0]))

        del kwargs['show_command']

    subprocess_run(*args, **kwargs)


def run_only_print_errors(*args, **kwargs):
    '''Wrapper for run, to show the commands being run.'''
    kwargs.update({
        'show_command': False,
        'stdout': PIPE,
        'stderr': PIPE
    })
    run(*args, **kwargs)


def sha256_hexdigest(content_bytes):
    '''Generate a SHA256 digest of some bytes.'''
    hashval = hashlib.sha256()
    hashval.update(content_bytes)
    return hashval.hexdigest()


def yield_chunks(fileobj):
    '''Yield chunks from a fileobj.'''
    while True:
        chunk = fileobj.read(1024)
        if not chunk:
            break

        yield chunk


def sha256_hexdigest_path(path):
    '''Generate a sha256 digest of a file at the given path.'''
    with open(path, 'rb') as fileobj:
        hashval = hashlib.sha256()
        for chunk in yield_chunks(fileobj):
            hashval.update(chunk)

    return hashval.hexdigest()


SubscriptionsLocation = namedtuple('SubscriptionsLocation',
                                   'shard subscriptions_json subscription_id')


def generate_subscriptions_locations(app_id, output_directory):
    '''Generate a valid path for a shard location.'''
    hash_app_id = sha256_hexdigest(app_id.encode('utf-8'))
    subs_path = os.path.join(output_directory,
                             'share',
                             'ekn',
                             'data',
                             app_id,
                             'com.endlessm.subscriptions',
                             hash_app_id)

    os.makedirs(subs_path, exist_ok=True)

    return SubscriptionsLocation(shard=os.path.join(subs_path, 'content.shard'),
                                 subscriptions_json=os.path.join(subs_path,
                                                                 'manifest.json'),
                                 subscription_id=hash_app_id)


def find_xapian_db_offset(shard_path):
    '''Open the shard and work out where the Xapian database is.'''
    # Having to linear-search the shard like this seems wasteful, but it
    # does not look like there is a clear way to look up the xapian
    # database by a content-type index.
    shard = EosShard.ShardFile(path=shard_path)
    shard.init(None)
    for record in shard.list_records():
        for blob in record.list_blobs():
            if blob.get_content_type() == 'application/x-endlessm-xapian-db':
                return blob.get_offset()

    raise RuntimeError('Could not find a Xapian database in {}'.format(shard_path))


def compile_content_into_subscription(db_json_path,
                                      subscriptions):
    '''Run basin from the system to build the app database.

    Note that we need to run the system-level basin here since we are
    testing using the system-level knowledge-lib and database versions
    can differ between SDKs.
    '''
    run_only_print_errors([
        'basin',
        os.path.basename(db_json_path),
        subscriptions.shard
    ], cwd=os.path.dirname(db_json_path))
    timestamp = datetime.now().isoformat()
    with open(subscriptions.subscriptions_json, 'w') as subscriptions_json_f:
        json.dump({
            'version': '1',
            'timestamp': timestamp,
            'subscription_id': subscriptions.subscription_id,
            'xapian_databases': [
                {
                    'offset': find_xapian_db_offset(subscriptions.shard),
                    'path': 'content.shard'
                }
            ],
            'shards': [
                {
                    'id': 'content',
                    'path': 'content.shard',
                    'published_timestamp': timestamp,
                    'sha256_csum': sha256_hexdigest_path(subscriptions.shard),
                    'category_tags': []
                }
            ]
        }, fp=subscriptions_json_f)


def generate_resources_location(app_id, output_directory):
    '''Generate a location for the GResources file.'''
    directory = os.path.join(output_directory, 'share', app_id)
    os.makedirs(directory, exist_ok=True)

    return os.path.join(directory, 'app.gresource')


def build_gresource_document_string():
    '''Build a GResource manifest for the app.

    Right now this assumes that the only thing in the resource will
    be the overrides.scss file.
    '''
    root = ET.Element('gresources')
    resource = ET.SubElement(root, 'gresource', attrib={
        'prefix': '/app'
    })
    file_tag = ET.Element('file')
    file_tag.text = 'overrides.scss'
    resource.append(file_tag)
    return '<?xml version="1.0" encoding="UTF-8"?>\n{}'.format(ET.tostring(root).decode())


def compile_gresource_file(app_resources_directory,
                           gresource_file_location):
    '''Use the glib-compile-resources tool to compile the app resources.'''
    with NamedTemporaryFile() as temp_fileobj:
        contents = build_gresource_document_string()
        temp_fileobj.write(contents.encode('utf-8'))
        temp_fileobj.flush()

        run_only_print_errors([
            'glib-compile-resources',
            '--target={}'.format(gresource_file_location),
            '--sourcedir={}'.format(app_resources_directory),
            temp_fileobj.name
        ])


def write_string_to_path(string, path):
    '''Write a string to a path.'''
    with open(path, 'w') as path_fileobj:
        path_fileobj.write(string)


def write_ekn_version(app_id, version, output_directory):
    '''Write the EKN_VERSION file to the application output_directory.'''
    path = os.path.join(output_directory,
                        'share',
                        'ekn',
                        'data',
                        app_id,
                        'EKN_VERSION')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_string_to_path(version, path)


def compile_app_structure(app_id, directory, output_directory):
    '''Build the assets for the app and assemble them into place.'''
    os.makedirs(output_directory, exist_ok=True)

    app_directory = os.path.join(directory, 'app')
    content_directory = os.path.join(directory, 'content')

    files_output_directory = os.path.join(output_directory, 'files')

    subscriptions = generate_subscriptions_locations(app_id,
                                                     files_output_directory)
    compile_content_into_subscription(os.path.join(content_directory,
                                                   'db.json'),
                                      subscriptions)

    resources = generate_resources_location(app_id, files_output_directory)
    compile_gresource_file(app_directory,
                           resources)

    write_ekn_version(app_id, '3', files_output_directory)
    applications_directory = os.path.join(files_output_directory,
                                          'share',
                                          'applications')
    icons_directory = os.path.join(files_output_directory,
                                   'share',
                                   'icons',
                                   'hicolor',
                                   '64x64',
                                   'apps')

    os.makedirs(applications_directory, exist_ok=True)
    os.makedirs(icons_directory, exist_ok=True)

    shutil.copy(os.path.join(app_directory, '{}.desktop'.format(app_id)),
                applications_directory)
    shutil.copy(os.path.join(app_directory, '{}.png'.format(app_id)),
                icons_directory)

    binpath = os.path.join(files_output_directory, 'bin')
    os.makedirs(binpath, exist_ok=True)
    write_string_to_path('#!/bin/bash\n',
                         os.path.join(binpath, app_id))


def build_flatpak_app(app_id,
                      directory,
                      output_directory,
                      repo_directory):
    '''Build a flatpak app from content in directory.'''
    os.makedirs(repo_directory, exist_ok=True)

    run_only_print_errors([
        'flatpak',
        'build-init',
        output_directory,
        app_id,
        'com.endlessm.apps.Sdk',
        'com.endlessm.apps.Platform',
        '3'
    ], check=True)
    compile_app_structure(app_id, directory, output_directory)
    run_only_print_errors([
        'flatpak',
        'build-finish',
        output_directory,
        '--command',
        app_id
    ], check=True)
    run_only_print_errors([
        'flatpak',
        'build-export',
        repo_directory,
        output_directory,
        'master'
    ], check=True)


def install_flatpak_app(app, install_directory):
    '''Install a flatpak app from the repo to install_directory.'''
    os.makedirs(install_directory, exist_ok=True)
    environment = os.environ.copy()
    environment.update({
        'FLATPAK_USER_DIR': install_directory
    })

    run_only_print_errors([
        'flatpak',
        'install',
        '--user',
        'test-apps',
        app
    ], env=environment, check=True)


def force_remove_directory(directory):
    '''Forcibly remove a directory, ignoring ENOENT.'''
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        pass


@contextmanager
def temporary_directory(parent_directory=None):
    '''Context that creates a temporary directory and removes it on exit.'''
    try:
        directory = mkdtemp(dir=parent_directory)
        yield directory
    finally:
        force_remove_directory(directory)


def format_runtime(name, branch):
    '''Format a runtime name with our architecture.'''
    return '{name}/{arch}/{branch}'.format(name=name,
                                           arch=Flatpak.get_default_arch(),
                                           branch=branch)


def setup_fake_apps_runtime(repo_directory, install_directory):
    '''Setup a fake com.endlessm.apps.Platform runtime and install it.

    We'll build the apps using the actual runtime and SDK, but install
    a fake one so that we don't chew up disk space and bandwidth during tests.
    '''
    os.makedirs(repo_directory, exist_ok=True)

    with temporary_directory() as working_directory:
        runtime_metadata_keyfile = GLib.KeyFile()
        runtime_metadata_keyfile.set_string('Runtime',
                                            'name',
                                            'com.endlessm.apps.Platform')
        runtime_metadata_keyfile.set_string('Runtime',
                                            'runtime',
                                            format_runtime('com.endlessm.apps.Platform',
                                                           '3'))
        runtime_metadata_keyfile.save_to_file(os.path.join(working_directory,
                                                           'metadata'))

        os.makedirs(os.path.join(working_directory, 'usr'))
        os.makedirs(os.path.join(working_directory, 'files'))

        run_only_print_errors([
            'ostree',
            'init',
            '--mode=archive-z2',
            '--collection-id=org.test.CollectionId'
        ], cwd=working_directory, check=True)
        run_only_print_errors([
            'flatpak',
            'build-export',
            repo_directory,
            working_directory,
            '3'
        ], check=True)

    # Now that the runtime has been exported to the repo, install the flatpak
    environment = os.environ.copy()
    environment.update({
        'FLATPAK_USER_DIR': install_directory
    })
    run_only_print_errors([
        'flatpak',
        'remote-add',
        '--user',
        '--no-gpg-verify',
        'test-apps',
        repo_directory
    ], env=environment, check=True)
    install_flatpak_app('com.endlessm.apps.Platform//3',
                        install_directory)


def setup_fake_apps(apps, apps_directory, installation_directory):
    '''Set up some fake content app Flatpaks into installation_directory.'''
    force_remove_directory(installation_directory)
    os.makedirs(installation_directory)

    with temporary_directory() as build_directory:
        repo_directory = os.path.join(build_directory, 'repo')
        compile_directory = os.path.join(build_directory, 'build')

        # Install the fake runtime first, so that we
        # can install the fake apps
        setup_fake_apps_runtime(repo_directory, installation_directory)

        for app_id in apps:
            build_flatpak_app(app_id,
                              os.path.join(apps_directory, app_id),
                              os.path.join(compile_directory, app_id),
                              repo_directory)
            install_flatpak_app(app_id, installation_directory)