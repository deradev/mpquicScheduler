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

from time import strftime
import os
# The configuration file for the AStream module
# create logger
LOG_NAME = 'AStream_log'
LOG_LEVEL = None

# Set '-' to print to screen
LOG_FOLDER = "ASTREAM_LOGS/"
if not os.path.exists(LOG_FOLDER):
    os.makedirs(LOG_FOLDER)

LOG_FILENAME = os.path.join(LOG_FOLDER, 'DASH_RUNTIME_LOG')
# Logs related to the statistics for the video
# PLAYBACK_LOG_FILENAME = os.path.join(LOG_FOLDER, strftime('DASH_PLAYBACK_LOG_%Y-%m-%d.%H_%M_%S.csv'))
# Buffer logs created by dash_buffer.py
BUFFER_LOG_FILENAME = os.path.join(LOG_FOLDER, strftime('DASH_BUFFER_LOG_%Y-%m-%d.%H_%M_%S.csv'))
LOG_FILE_HANDLE = None
# To be set by configure_log_file.py
LOG = None
# JSON Filename
JSON_LOG = os.path.join(LOG_FOLDER, strftime('ASTREAM_%Y-%m-%d.%H_%M_%S.json'))
JSON_HANDLE = dict()
JSON_HANDLE['playback_info'] = {'start_time': None,
                                'end_time': None,
                                'initial_buffering_duration': None,
                                'interruptions': {'count': 0, 'events': list(), 'total_duration': 0},
                                'up_shifts': 0,
                                'down_shifts': 0
                                }
# Constants for the BASIC-2 adaptation scheme
BASIC_THRESHOLD = 10
BASIC_UPPER_THRESHOLD = 1.2
# Number of segments for moving average
BASIC_DELTA_COUNT = 5

# ---------------------------------------------------
# SARA (Segment Aware Rate Adaptation)
# ---------------------------------------------------
# Number of segments for moving weighted average
SARA_SAMPLE_COUNT = 5
# Constants for the Buffer in the Weighted adaptation scheme (in segments)
INITIAL_BUFFERING_COUNT = 2
RE_BUFFERING_COUNT = 1
ALPHA_BUFFER_COUNT = 5
BETA_BUFFER_COUNT = 10
# Set the size of the buffer in terms of segments. Set to unlimited if 0 or None
MAX_BUFFER_SIZE = None

# ---------------------------------------------------
# Netflix (Buffer-based) ADAPTATION
# ---------------------------------------------------
# Constants for the Netflix Buffering scheme adaptation/netflix_buffer.py
# Constants is terms of buffer occupancy PERCENTAGE(%)
NETFLIX_RESERVOIR = 0.1
NETFLIX_CUSHION = 0.9
# Buffer Size in Number of segments 240/4
NETFLIX_BUFFER_SIZE = 60
NETFLIX_INITIAL_BUFFER = 2
NETFLIX_INITIAL_FACTOR = 0.875

# For ping.py
PING_PACKETS = 10
ping_option_nb_pkts = PING_PACKETS
rtt_match = None
rtt_pattern = None
index_rtt_min = None
index_rtt_avg = None
index_rtt_max = None
RTT = False