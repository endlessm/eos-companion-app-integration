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
        'show_command': True,
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


def force_remove_directory(directory):
    '''Forcibly remove a directory, ignoring ENOENT.'''
    try:
        shutil.rmtree(directory)
    except FileNotFoundError:
        pass


def install_app(app, output_directory, install_directory):
    '''Install a flatpak app from the repo to install_directory.'''
    target_directory = os.path.join(install_directory,
                                    'app',
                                    app,
                                    'current',
                                    'active')

    # Now, for copytree to work, we need to make all the directory
    # parents, but remove the target directory
    os.makedirs(target_directory, exist_ok=True)
    force_remove_directory(target_directory)
    shutil.copytree(output_directory, target_directory)

    # Create the metadata file
    app_metadata_keyfile = GLib.KeyFile()
    app_metadata_keyfile.set_string('Application',
                                    'name',
                                    app)
    app_metadata_keyfile.set_string('Application',
                                    'runtime',
                                    format_runtime('com.endlessm.apps.Platform',
                                                   '3'))
    app_metadata_keyfile.set_string('Application',
                                    'sdk',
                                    format_runtime('com.endlessm.apps.Sdk',
                                                   '3'))
    app_metadata_keyfile.set_string('Application',
                                    'command',
                                    app)
    app_metadata_keyfile.save_to_file(os.path.join(target_directory,
                                                   'metadata'))

    # Export the /share tree
    app_share_dir = os.path.join(target_directory, 'files', 'share')

    # Exporting the local exports dir is fairly straightforward, just create
    # a directory level symlink
    app_exports_dir = os.path.join(target_directory, 'exports')
    os.makedirs(app_exports_dir, exist_ok=True)
    os.symlink(app_share_dir, os.path.join(app_exports_dir, 'share'))

    # Exporting into the global exports dir is a little trickier, we need
    # to walk the directory tree of the app exports dir and create
    # any corresponding directories in the global exports directory
    #
    # A file already existing in place of a symbolic link is an error
    global_exports_dir = os.path.join(install_directory, 'exports')
    os.makedirs(global_exports_dir, exist_ok=True)

    for root, directories, filenames in os.walk(app_exports_dir, followlinks=True):
        # Directory and file names are relative to 'root', which changes
        # as we explore directories. Get the relative path from root
        # to app_exports_dir so that we can join it
        root_relative = os.path.relpath(root, app_exports_dir)

        for directory in directories:
            os.makedirs(os.path.join(global_exports_dir,
                                     root_relative,
                                     directory), exist_ok=True)

        for filename in filenames:
            os.link(os.path.join(root, filename),
                    os.path.join(global_exports_dir, root_relative, filename))


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


def setup_fake_apps(apps, apps_directory, installation_directory):
    '''Set up some fake content app Flatpaks into installation_directory.'''
    force_remove_directory(installation_directory)
    os.makedirs(installation_directory)

    with temporary_directory() as build_directory:
        compile_directory = os.path.join(build_directory, 'build')
        force_remove_directory(installation_directory)

        for app_id in apps:
            compile_app_structure(app_id,
                                  os.path.join(apps_directory, app_id),
                                  os.path.join(compile_directory, app_id))
            install_app(app_id,
                        os.path.join(compile_directory, app_id),
                        installation_directory)
