# /eoscompanion/functional.py
#
# Copyright (C) 2017, 2018 Endless Mobile, Inc.
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
'''Functional programming helpers.'''


def all_asynchronous_function_calls_closure(calls, done_callback):
    '''Wait for each function call in calls to complete, then pass results.

    Call each single-argument function in calls, storing the resulting
    tuple of arguments in the corresponding array entry and passing the entire
    array back to done_callback.

    The single-argument to each member of calls is expected to be a callback
    function that the caller can pass to determine when the asynchronous
    operation is complete.
    '''
    def callback_thunk(index):
        '''A thunk to keep track of the index of a given call.'''
        def callback(*args):
            '''A callback for the asynchronous function, packing *args.'''
            nonlocal remaining

            results[index] = args

            remaining -= 1
            if remaining == 0:
                done_callback(results)

        return callback

    # Some state we will need to keep track of whilst the calls are ongoing
    remaining = len(calls)

    # Nothing to do. Can return immediately:
    if remaining == 0:
        done_callback([])
        return

    results = [None for c in calls]

    for i, call in enumerate(calls):
        call(callback_thunk(i))
