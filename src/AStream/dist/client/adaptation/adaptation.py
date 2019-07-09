"""
Adaptation algorithms
1. basic_dash
2. weighted_dash
"""

from __future__ import division


def calculate_rate_index(bitrates, curr_rate):
    """ Module that finds the bitrate closes to the curr_rate
    :param bitrates: LIst of available bitrates
    :param curr_rate: current_bitrate
    :return: curr_rate_index
    """
    if curr_rate < bitrates[0]:
        return bitrates[0]
    elif curr_rate > bitrates[-1]:
        return bitrates[-1]
    else:
        for bitrate, index in enumerate(bitrates[1:]):
            if bitrates[index-1] < curr_rate < bitrate:
                return curr_rate


class WeightedMean:
    """ Harmonic mean.
        The weights are the sizes of the segments
    """
    def __init__(self, sample_count):
        # List of (size, download_rate)
        self.segment_info = list()
        self.weighted_mean_rate = 0
        self.sample_count = sample_count

    def update_weighted_mean(self, segment_size, segment_download_time):
        """ Method to update the weighted harmonic mean for the segments.
            segment_size is in bytes
            segment_download_time is in seconds
            http://en.wikipedia.org/wiki/Harmonic_mean#Weighted_harmonic_mean
        """
        segment_download_rate = segment_size / segment_download_time
        while len(self.segment_info) > self.sample_count:
            self.segment_info.pop(0)
        self.segment_info.append((segment_size, segment_download_rate))
        self.weighted_mean_rate = sum([size for size, _ in self.segment_info]) / sum([s/r for s, r in self.segment_info])
        return self.weighted_mean_rate

