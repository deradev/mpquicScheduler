__author__ = 'pjuluri'

import config_dash


def weighted_dash(bitrates, dash_player, weighted_dwn_rate, curr_bitrate, next_segment_sizes):
    """
    Module to predict the next_bitrate using the weighted_dash algorithm
    :param bitrates: List of bitrates
    :param weighted_dwn_rate:
    :param curr_bitrate:
    :param next_segment_sizes: A dict mapping bitrate: size of next segment
    :return: next_bitrate, delay
    """
    bitrates = [int(i) for i in bitrates]
    bitrates.sort()
    # Waiting time before downloading the next segment
    delay = 0
    next_bitrate = None
    available_video_segments = dash_player.buffer.qsize() - dash_player.initial_buffer
    # If the buffer is less that the Initial buffer, playback remains at th lowest bitrate
    # i.e dash_buffer.current_buffer < dash_buffer.initial_buffer
    available_video_duration = available_video_segments * dash_player.segment_duration
    config_dash.LOG.debug("Buffer_length = {} Initial Buffer = {} Available video = {} seconds, alpha = {}. "
                          "Beta = {} WDR = {}, curr Rate = {}".format(dash_player.buffer.qsize(),
                                                                      dash_player.initial_buffer,
                                                                      available_video_duration, dash_player.alpha,
                                                                      dash_player.beta, weighted_dwn_rate,
                                                                      curr_bitrate))

    if weighted_dwn_rate == 0 or available_video_segments == 0:
        next_bitrate = bitrates[0]
    # If time to download the next segment with current bitrate is longer than current - initial,
    # switch to a lower suitable bitrate

    elif float(next_segment_sizes[curr_bitrate])/weighted_dwn_rate > available_video_duration:
        config_dash.LOG.debug("next_segment_sizes[curr_bitrate]) weighted_dwn_rate > available_video")
        for bitrate in reversed(bitrates):
            if bitrate < curr_bitrate:
                if float(next_segment_sizes[bitrate])/weighted_dwn_rate < available_video_duration:
                    next_bitrate = bitrate
                    break
        if not next_bitrate:
            next_bitrate = bitrates[0]
    elif available_video_segments <= dash_player.alpha:
        config_dash.LOG.debug("available_video <= dash_player.alpha")
        if curr_bitrate >= max(bitrates):
            config_dash.LOG.info("Current bitrate is MAX = {}".format(curr_bitrate))
            next_bitrate = curr_bitrate
        else:
            higher_bitrate = bitrates[bitrates.index(curr_bitrate)+1]
            # Jump only one if suitable else stick to the current bitrate
            config_dash.LOG.info("next_segment_sizes[higher_bitrate] = {}, weighted_dwn_rate = {} , "
                                 "available_video={} seconds, ratio = {}".format(next_segment_sizes[higher_bitrate],
                                                                                 weighted_dwn_rate,
                                                                                 available_video_duration,
                                                                                float(next_segment_sizes[higher_bitrate])/weighted_dwn_rate))
            if float(next_segment_sizes[higher_bitrate])/weighted_dwn_rate < available_video_duration:
                next_bitrate = higher_bitrate
            else:
                next_bitrate = curr_bitrate
    elif available_video_segments <= dash_player.beta:
        config_dash.LOG.debug("available_video <= dash_player.beta")
        if curr_bitrate >= max(bitrates):
            next_bitrate = curr_bitrate
        else:
            for bitrate in reversed(bitrates):
                if bitrate >= curr_bitrate:
                    if float(next_segment_sizes[bitrate])/weighted_dwn_rate < available_video_duration:
                        next_bitrate = bitrate
                        break
            if not next_bitrate:
                next_bitrate = curr_bitrate

    elif available_video_segments > dash_player.beta:
        config_dash.LOG.debug("available_video > dash_player.beta")
        if curr_bitrate >= max(bitrates):
            next_bitrate = curr_bitrate
        else:
            for bitrate in reversed(bitrates):
                if bitrate >= curr_bitrate:
                    if float(next_segment_sizes[bitrate])/weighted_dwn_rate > available_video_duration:
                        next_bitrate = bitrate
                        break
        if not next_bitrate:
            next_bitrate = curr_bitrate
        delay = dash_player.buffer.qsize() - dash_player.beta
        config_dash.LOG.info("Delay:{}".format(delay))
    else:
        next_bitrate = curr_bitrate
    config_dash.LOG.debug("The next_bitrate is assigned as {}".format(next_bitrate))
    return next_bitrate, delay
