#!/usr/bin/env python
from __future__ import with_statement, absolute_import
import os
import re
import platform
import config_dash
from configure_log_file import configure_log_file

"""Module to generate the RTT times of a ping
   This module provides two functions that enable us to get the ping statistics
   of an IP address on any system(Linux, Windows, Mac)

"""


if not config_dash.LOG:
    configure_log_file()

RTT_MATCH_LINUX = r"rtt min/avg/max/mdev = "
RTT_PATTERN_LINUX = r"(\d+.\d+)/(\d+.\d+)/(\d+.\d+)/\d+.\d+ ms"
PING_OPTION_LINUX = '-c'

RTT_MATCH_WINDOWS = r"Minimum = "
#if 'LANG' in os.environ and os.environ['LANG'] == 'FR':
RTT_PATTERN_WINDOWS = (
    r"(\d+)ms, Maximum = (\d+)ms, (?:Moyenne|Average) = (\d+)ms")
#else:
#    RTT_PATTERN_WINDOWS = (
#        r"(\d+)ms, Maximum = (\d+)ms, Average = (\d+)ms")
PING_OPTION_WINDOWS = '-n'

RTT_MATCH_DARWIN = "round-trip min/avg/max/stddev = "
RTT_PATTERN_DARWIN = RTT_PATTERN_LINUX
PING_OPTION_DARWIN = PING_OPTION_LINUX


def configure_ping_options(ping_packets=config_dash.PING_PACKETS):
    """Store in config_pytomo module the config for RTT matching"""
    system = platform.system().lower()
    if system.startswith('linux'):
        config_dash.ping_option_nb_pkts = ' '.join((PING_OPTION_LINUX, str(ping_packets)))
        config_dash.rtt_match = RTT_MATCH_LINUX
        config_dash.rtt_pattern = ''.join((RTT_MATCH_LINUX, RTT_PATTERN_LINUX))
        config_dash.index_rtt_min = 0
        config_dash.index_rtt_avg = 1
        config_dash.index_rtt_max = 2

    elif (system.startswith('microsoft')
          or system.startswith('windows')):
        config_dash.ping_option_nb_pkts = ' '.join((PING_OPTION_WINDOWS, str(ping_packets)))
        config_dash.rtt_match = RTT_MATCH_WINDOWS
        config_dash.rtt_pattern = ''.join((RTT_MATCH_WINDOWS, RTT_PATTERN_WINDOWS))

        # windows pings present max before avg
        config_dash.index_rtt_min = 0
        config_dash.index_rtt_avg = 2
        config_dash.index_rtt_max = 1

    elif system.startswith('darwin'):
        config_dash.ping_option_nb_pkts = ' '.join((PING_OPTION_DARWIN, str(ping_packets)))
        config_dash.rtt_match = RTT_MATCH_DARWIN
        config_dash.rtt_pattern = ''.join((RTT_MATCH_DARWIN, RTT_PATTERN_DARWIN))
        config_dash.index_rtt_min = 0
        config_dash.index_rtt_avg = 1
        config_dash.index_rtt_max = 2

    else:
        config_dash.LOG.warn("Ping option is not known on your system: %s"
                             % config_dash.SYSTEM)
        return None
    config_dash.RTT = True


def ping_ip(ip_address, ping_packets=config_dash.PING_PACKETS, verbose=False):
    "Return a list of the min, avg, max and mdev ping values"
    if not config_dash.RTT:
        configure_ping_options(ping_packets)
        if not config_dash.RTT:
            config_dash.LOG.warn("Not able to process ping on your system")
            return None
    ping_cmd = 'ping %s %s' % (config_dash.ping_option_nb_pkts, ip_address)
    ping_result = os.popen(ping_cmd)
    rtt_stats = None
    # instead of grep which is less portable
    # use of readlines for windows output :(
    for rtt_line in ping_result.readlines():
        if config_dash.rtt_match in rtt_line:
            rtt_stats = rtt_line.strip()
            break
    if not rtt_stats:
        config_dash.LOG.info("No RTT stats found")
        return None
    rtt_times = re.search(config_dash.rtt_pattern, rtt_stats)
    if rtt_times:
        rtt_values = rtt_times.groups()
        rtt_values = [rtt_values[config_dash.index_rtt_min],
                      rtt_values[config_dash.index_rtt_avg],
                      rtt_values[config_dash.index_rtt_max]]

        config_dash.LOG.debug(
            "RTT stats found for ip: %s" % ip_address)
        return map(float, rtt_values)
    config_dash.LOG.error(
        "The ping returned an unexpected RTT fomat: %s" % rtt_stats)
    return None
