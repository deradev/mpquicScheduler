#!/usr/bin/env python

from __future__ import division
__author__ = 'pjuluri'

"""
 The current module is the buffer based adaptaion scheme used by Netflix. Current design is based
 on the design from the paper:

[1] Huang, Te-Yuan, et al. "A buffer-based approach to rate adaptation: Evidence from a large video streaming service."
    Proceedings of the 2014 ACM conference on SIGCOMM. ACM, 2014.
"""

import config_dash
from collections import OrderedDict


def get_rate_map(bitrates):
    """
    Module to generate the rate map for the bitrates, reservoir, and cushion
    """
    rate_map = OrderedDict()
    rate_map[config_dash.NETFLIX_RESERVOIR] = bitrates[0]
    intermediate_levels = bitrates[1:-1]
    marker_length = (config_dash.NETFLIX_CUSHION - config_dash.NETFLIX_RESERVOIR)/(len(intermediate_levels)+1)
    current_marker = config_dash.NETFLIX_RESERVOIR + marker_length
    for bitrate in intermediate_levels:
        rate_map[current_marker] = bitrate
        current_marker += marker_length
    rate_map[config_dash.NETFLIX_CUSHION] = bitrates[-1]
    return rate_map


def get_rate_netflix(bitrates, current_buffer_occupancy, buffer_size=config_dash.NETFLIX_BUFFER_SIZE, rate_map=None):
    """
    Module that estimates the next bitrate basedon the rate map.
    Rate Map: Buffer Occupancy vs. Bitrates:
        If Buffer Occupancy < RESERVOIR (10%) :
            select the minimum bitrate
        if RESERVOIR < Buffer Occupancy < Cushion(90%) :
            Linear function based on the rate map
        if Buffer Occupancy > Cushion :
            Maximum Bitrate
    Ref. Fig. 6 from [1]

    :param current_buffer_occupancy: Current buffer occupancy in number of segments
    :param bitrates: List of available bitrates [r_min, .... r_max]
    :return:the bitrate for the next segment
    """
    next_bitrate = None
    try:
        bitrates = [int(i) for i in bitrates]
        bitrates.sort()
    except ValueError:
        config_dash.LOG.error("Unable to sort the bitrates. Assuming they are sorted")
    # Calculate the current buffer occupancy percentage
    try:
        buffer_percentage = current_buffer_occupancy/buffer_size
        print buffer_percentage
    except ZeroDivisionError:
        config_dash.LOG.error("Buffer Size was found to be Zero")
        return None
    # Selecting the next bitrate based on the rate map
    if not rate_map:
        rate_map = get_rate_map(bitrates)
    if buffer_percentage <= config_dash.NETFLIX_RESERVOIR:
        next_bitrate = bitrates[0]
    elif buffer_percentage >= config_dash.NETFLIX_CUSHION:
        next_bitrate = bitrates[-1]
    else:
        config_dash.LOG.info("Rate Map: {}".format(rate_map))
        for marker in reversed(rate_map.keys()):
            if marker < buffer_percentage:
                break
            next_bitrate = rate_map[marker]
    return next_bitrate


def netflix_dash(bitrates, dash_player, segment_download_rate, curr_bitrate, average_segment_sizes, rate_map, state):
    """
    Netflix rate adaptation module
    """
    available_video_segments = dash_player.buffer.qsize() - dash_player.initial_buffer
    if not (curr_bitrate or rate_map or state):
        rate_map = get_rate_map(bitrates)
        state = "INITIAL"
        next_bitrate = bitrates[0]
    elif state == "INITIAL":
        # if the B increases by more than 0.875V s. Since B = V - ChunkSize/c[k],
        # B > 0:875V also means that the chunk is downloaded eight times faster than it is played
        next_bitrate = curr_bitrate
        # delta-B = V - ChunkSize/c[k]
        delta_B = dash_player.segment_duration - average_segment_sizes[curr_bitrate]/segment_download_rate
        # Select the higher bitrate as long as delta B > 0.875 * V
        if delta_B > config_dash.NETFLIX_INITIAL_FACTOR * dash_player.segment_duration:
            next_bitrate = bitrates[bitrates.index(curr_bitrate)+1]
        # if the current buffer occupancy is less that NETFLIX_INITIAL_BUFFER, then do NOY use rate map
        if not available_video_segments < config_dash.NETFLIX_INITIAL_BUFFER:

            # get the next bitrate based on the ratemap
            rate_map_next_bitrate = get_rate_netflix(bitrates, available_video_segments,
                                                     config_dash.NETFLIX_BUFFER_SIZE, rate_map)
            # Consider the rate map only if the rate map gives a higher value.
            # Once the rate mao returns a higher value exit the 'INITIAL' stage
            if rate_map_next_bitrate > next_bitrate:
                next_bitrate = rate_map_next_bitrate
                state = "RUNNING"
    else:
        next_bitrate = get_rate_netflix(bitrates, available_video_segments, config_dash.NETFLIX_BUFFER_SIZE, rate_map)
    return next_bitrate, rate_map, state