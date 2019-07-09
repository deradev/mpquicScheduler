#!/usr/bin/env python
#
#    AStream: Python based DASH player emulator to evaluate the rate adaptation algorithms
#             for DASH.
#    Copyright (C) 2015, Parikshit Juluri
#
#    This program is free software; you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation; either version 2 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License along
#    with this program; if not, write to the Free Software Foundation, Inc.,
#    51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.
#

import dash_buffer
import time
import copy

SEGMENT = {'playback_length':4,
           'size': 1024,
           'bitrate': 120,
           'data': "<byte data>",
           'URI': "URL of the segment",
           'segment_number': 0}
# SEGMENT_ARRIVAL_TIMES = [1, 2, 3, 4, 5]
SEGMENT_ARRIVAL_TIMES = [0, 2, 7, 14, 19]
# SEGMENT_ARRIVAL_TIMES = [0, 1, 3, 19, 26]


def run_test(segment_arrival_times=SEGMENT_ARRIVAL_TIMES):
    """
    :param segment_arrival_times: list of times the segement is loaded into the buffer
    :return: None
    """
    db = dash_buffer.DashBuffer(20)
    start_time = time.time()
    db.start()
    for count, arrival_time in enumerate(segment_arrival_times):
        segment = copy.deepcopy(SEGMENT)
        while True:
            actual_time = time.time() - start_time
            if arrival_time <= actual_time <= arrival_time + 1:
                segment['segment_number'] = count + 1
                db.write(segment)
                break
            if actual_time > arrival_time:
                print "ERROR: Missed the time slot for segemt {}".format(count)
                break
            time.sleep(1)
    if time.time() - start_time >= 40:
        print "Killing the player after 40 seconds"
        db.stop()


run_test()