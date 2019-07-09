#!/usr/local/bin/python
"""
Author:            Parikshit Juluri
Contact:           pjuluri@umkc.edu
Testing:
    import dash_client
    mpd_file = <MPD_FILE>
    dash_client.playback_duration(mpd_file, 'http://198.248.242.16:8005/')

    From commandline:
    python dash_client.py -m "http://198.248.242.16:8006/media/mpd/x4ukwHdACDw.mpd" -p "all"
    python dash_client.py -m "http://127.0.0.1:8000/media/mpd/x4ukwHdACDw.mpd" -p "basic"

"""
from __future__ import division
import conn as glueConnection
import read_mpd
import urlparse
import urllib2
#import httplib
import ssl
import socket
import struct
import random
import os
import sys
import errno
import timeit
from string import ascii_letters, digits
from argparse import ArgumentParser
from multiprocessing import Process, Queue
from collections import defaultdict
from adaptation import basic_dash, basic_dash2, weighted_dash, netflix_dash
from adaptation.adaptation import WeightedMean
import config_dash
import dash_buffer
from configure_log_file import configure_log_file, write_json
import time

try:
    WindowsError
except NameError:
    from shutil import WindowsError

# Constants
DEFAULT_PLAYBACK = 'BASIC'
DOWNLOAD_CHUNK = 1024

# Globals for arg parser with the default values
# Not sure if this is the correct way ....
MPD = None
LIST = False
PLAYBACK = DEFAULT_PLAYBACK
DOWNLOAD = False
SEGMENT_LIMIT = None
# Settings for the download connection
QUIC = False
MP = False
NO_KEEP_ALIVE = False
SCHEDULER = 'lowRTT'

lastTime = None
procTimes = list()

class DashPlayback:
    """
    Audio[bandwidth] : {duration, url_list}
    Video[bandwidth] : {duration, url_list}
    """
    def __init__(self):

        self.min_buffer_time = None
        self.playback_duration = None
        self.audio = dict()
        self.video = dict()


def get_mpd(url):
    """ Module to download the MPD from the URL and save it to file"""
    #print url
    try:
        if url.find('https://') == 0:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            connection = urllib2.urlopen(url, timeout=10, context=ctx)
        else:
            connection = urllib2.urlopen(url, timeout=10)
    except urllib2.HTTPError, error:
        config_dash.LOG.error("Unable to download MPD file HTTP Error: %s" % error.code)
        return None
    except urllib2.URLError:
        error_message = "URLError. Unable to reach Server.Check if Server active"
        config_dash.LOG.error(error_message)
        print error_message
        return None
    except IOError, httplib.HTTPException:
        message = "Unable to , file_identifierdownload MPD file HTTP Error."
        config_dash.LOG.error(message)
        return None
    
    mpd_data = connection.read()
    connection.close()
    mpd_file = url.split('/')[-1]
    mpd_file_handle = open(mpd_file, 'w')
    mpd_file_handle.write(mpd_data)
    mpd_file_handle.close()
    config_dash.LOG.info("Downloaded the MPD file {}".format(mpd_file))
    return mpd_file


def get_bandwidth(data, duration):
    """ Module to determine the bandwidth for a segment
    download"""
    return data * 8/duration


def get_domain_name(url):
    """ Module to obtain the domain name from the URL
        From : http://stackoverflow.com/questions/9626535/get-domain-name-from-url
    """
    parsed_uri = urlparse.urlparse(url)
    domain = '{uri.scheme}://{uri.netloc}/'.format(uri=parsed_uri)
    return domain


def id_generator(id_size=6):
    """ Module to create a random string with uppercase 
        and digits.
    """
    return 'TEMP_' + ''.join(random.choice(ascii_letters+digits) for _ in range(id_size))

def download_segment(segment_url, dash_folder):
    """ Module to download the segment """
    try:
        connection = urllib2.urlopen(segment_url)
    except urllib2.HTTPError, error:
        config_dash.LOG.error("Unable to download DASH Segment {} HTTP Error:{} ".format(segment_url, str(error.code)))
        return None
    parsed_uri = urlparse.urlparse(segment_url)
    segment_path = '{uri.path}'.format(uri=parsed_uri)
    while segment_path.startswith('/'):
        segment_path = segment_path[1:]        
    segment_filename = os.path.join(dash_folder, os.path.basename(segment_path))
    make_sure_path_exists(os.path.dirname(segment_filename))
    segment_file_handle = open(segment_filename, 'wb')
    segment_size = 0
    while True:
        segment_data = connection.read(DOWNLOAD_CHUNK)
        segment_size += len(segment_data)
        segment_file_handle.write(segment_data)
        if len(segment_data) < DOWNLOAD_CHUNK:
            break
    connection.close()
    segment_file_handle.close()
    #print "segment size = {}".format(segment_size)
    #print "segment filename = {}".format(segment_filename)
    return segment_size, segment_filename

def download_segment_efficient(segment_url, dash_folder):
    """ Module to download the segment with one
        permanent HTTP connection.
    """
    cropped_fInd = segment_url.rfind('/')
    segment_name = segment_url[cropped_fInd:len(segment_url)]
    glueConnection.startLogging(1000)
    segment_size = glueConnection.download_segment_PM(segment_url)
    return segment_size, segment_name

def get_media_all(domain, media_info, file_identifier, done_queue):
    """ Download the media from the list of URL's in media
    """
    bandwidth, media_dict = media_info
    media = media_dict[bandwidth]
    media_start_time = timeit.default_timer()
    for segment in [media.initialization] + media.url_list:
        start_time = timeit.default_timer()
        segment_url = urlparse.urljoin(domain, segment)
        _, segment_file = download_segment(segment_url, file_identifier)
        elapsed = timeit.default_timer() - start_time
        if segment_file:
            done_queue.put((bandwidth, segment_url, elapsed))
    media_download_time = timeit.default_timer() - media_start_time
    done_queue.put((bandwidth, 'STOP', media_download_time))
    return None


def make_sure_path_exists(path):
    """ Module to make sure the path exists if not create it
    """
    try:
        os.makedirs(path)
    except OSError as exception:
        if exception.errno != errno.EEXIST:
            raise


def print_representations(dp_object):
    """ Module to print the representations"""
    print "The DASH media has the following video representations/bitrates"
    for bandwidth in dp_object.video:
        print bandwidth


def start_playback_smart(dp_object, domain, playback_type=None, download=False, video_segment_duration=None):
    """ Module that downloads the MPD-FIle and download
        all the representations of the Module to download
        the MPEG-DASH media.
        Example: start_playback_smart(dp_object, domain, "SMART", DOWNLOAD, video_segment_duration)

        :param dp_object:       The DASH-playback object
        :param domain:          The domain name of the server (The segment URLS are domain + relative_address)
        :param playback_type:   The type of playback
                                1. 'BASIC' - The basic adapataion scheme
                                2. 'SARA' - Segment Aware Rate Adaptation
                                3. 'NETFLIX' - Buffer based adaptation used by Netflix
        :param download: Set to True if the segments are to be stored locally (Boolean). Default False
        :param video_segment_duration: Playback duratoin of each segment
        :return:
    """
    # Initialize the DASH buffer
    dash_player = dash_buffer.DashPlayer(dp_object.playback_duration, video_segment_duration)
    dash_player.start()
    # A folder to save the segments in
    file_identifier = id_generator()
    config_dash.LOG.info("The segments are stored in %s" % file_identifier)
    dp_list = defaultdict(defaultdict)
    # Creating a Dictionary of all that has the URLs for each segment and different bitrates
    for bitrate in dp_object.video:
        # Getting the URL list for each bitrate
        dp_object.video[bitrate] = read_mpd.get_url_list(dp_object.video[bitrate], video_segment_duration,
                                                         dp_object.playback_duration, bitrate)

        if "$Bandwidth$" in dp_object.video[bitrate].initialization:
            dp_object.video[bitrate].initialization = dp_object.video[bitrate].initialization.replace(
                "$Bandwidth$", str(bitrate))
        media_urls = [dp_object.video[bitrate].initialization] + dp_object.video[bitrate].url_list
        #print "media urls"
        #print media_urls
        for segment_count, segment_url in enumerate(media_urls, dp_object.video[bitrate].start):
            # segment_duration = dp_object.video[bitrate].segment_duration
            #print "segment url"
            #print segment_url
            dp_list[segment_count][bitrate] = segment_url
    bitrates = dp_object.video.keys()
    bitrates.sort()
    global lastTime 
    global procTimes
    overall_avg_selected_rate = 0
    overall_avg_dwn_rate = 0
    overall_avg_dwn_time = 0
    overall_dwn_segments = 0
    average_dwn_rate = 0
    average_dwn_time = 0
    segment_files = []
    # For basic adaptation
    previous_segment_times = []
    recent_download_sizes = []
    weighted_mean_object = None
    current_bitrate = bitrates[0]
    previous_bitrate = None
    total_downloaded = 0
    # Delay in terms of the number of segments
    delay = 0
    segment_duration = 0
    segment_size = segment_download_time = None
    # Netflix Variables
    average_segment_sizes = netflix_rate_map = None
    netflix_state = "INITIAL"
    # Start playback of all the segments
    for segment_number, segment in enumerate(dp_list, dp_object.video[current_bitrate].start):
        config_dash.LOG.info(" {}: Processing the segment {}".format(playback_type.upper(), segment_number))
        write_json()
        if not previous_bitrate:
            previous_bitrate = current_bitrate
        if SEGMENT_LIMIT:
            if not dash_player.segment_limit:
                dash_player.segment_limit = int(SEGMENT_LIMIT)
            if segment_number > int(SEGMENT_LIMIT):
                config_dash.LOG.info("Segment limit reached")
                break
        #print "segment_number ={}".format(segment_number)
        #print "dp_object.video[bitrate].start={}".format(dp_object.video[bitrate].start)
        if segment_number == dp_object.video[bitrate].start:
            current_bitrate = bitrates[0]
        else:
            if playback_type.upper() == "BASIC":
                rates = basic_dash2.basic_dash2(segment_number, bitrates, average_dwn_time, recent_download_sizes, previous_segment_times, current_bitrate)
                
                current_bitrate = rates[0]
                average_dwn_time = rates[1]
                average_dwn_rate = rates[2]
                
                # Track network statistics
                overall_avg_dwn_time += average_dwn_time
                overall_avg_dwn_rate += average_dwn_rate
                overall_avg_selected_rate += current_bitrate

                if dash_player.buffer.qsize() > config_dash.BASIC_THRESHOLD:
                    delay = dash_player.buffer.qsize() - config_dash.BASIC_THRESHOLD
                config_dash.LOG.info("Basic-DASH: Selected {} for the segment {}".format(current_bitrate,
                                                                                         segment_number + 1))
            elif playback_type.upper() == "SMART":
                if not weighted_mean_object:
                    weighted_mean_object = WeightedMean(config_dash.SARA_SAMPLE_COUNT)
                    config_dash.LOG.debug("Initializing the weighted Mean object")
                # Checking the segment number is in acceptable range
                if segment_number < len(dp_list) - 1 + dp_object.video[bitrate].start:
                    try:
                        current_bitrate, delay = weighted_dash.weighted_dash(bitrates, dash_player,
                                                                             weighted_mean_object.weighted_mean_rate,
                                                                             current_bitrate,
                                                                             get_segment_sizes(dp_object,
                                                                                               segment_number+1))
                    except IndexError, e:
                        config_dash.LOG.error(e)

            elif playback_type.upper() == "NETFLIX":
                config_dash.LOG.info("Playback is NETFLIX")
                # Calculate the average segment sizes for each bitrate
                if not average_segment_sizes:
                    average_segment_sizes = get_average_segment_sizes(dp_object)
                if segment_number < len(dp_list) - 1 + dp_object.video[bitrate].start:
                    try:
                        if segment_size and segment_download_time:
                            segment_download_rate = segment_size / segment_download_time
                        else:
                            segment_download_rate = 0
                        current_bitrate, netflix_rate_map, netflix_state = netflix_dash.netflix_dash(
                            bitrates, dash_player, segment_download_rate, current_bitrate, average_segment_sizes,
                            netflix_rate_map, netflix_state)
                        config_dash.LOG.info("NETFLIX: Next bitrate = {}".format(current_bitrate))
                    except IndexError, e:
                        config_dash.LOG.error(e)
                else:
                    config_dash.LOG.critical("Completed segment playback for Netflix")
                    break

                # If the buffer is full wait till it gets empty
                if dash_player.buffer.qsize() >= config_dash.NETFLIX_BUFFER_SIZE:
                    delay = (dash_player.buffer.qsize() - config_dash.NETFLIX_BUFFER_SIZE + 1) * segment_duration
                    config_dash.LOG.info("NETFLIX: delay = {} seconds".format(delay))
            else:
                config_dash.LOG.error("Unknown playback type:{}. Continuing with basic playback".format(playback_type))
                current_bitrate, average_dwn_time = basic_dash.basic_dash(segment_number, bitrates, average_dwn_time,
                                                                          segment_download_time, current_bitrate)

        segment_path = dp_list[segment][current_bitrate]
        #print   "domain"
        #print domain
        #print "segment"
        #print segment
        #print "current bitrate"
        #print current_bitrate
        #print segment_path
        segment_url = urlparse.urljoin(domain, segment_path)
        #print "segment url"
        #print segment_url
        config_dash.LOG.info("{}: Segment URL = {}".format(playback_type.upper(), segment_url))
        if delay:
            delay_start = time.time()
            config_dash.LOG.info("SLEEPING for {}seconds ".format(delay*segment_duration))
            while time.time() - delay_start < (delay * segment_duration) - 0.001:
                time.sleep(0.001)
            delay = 0
            config_dash.LOG.debug("SLEPT for {}seconds ".format(time.time() - delay_start))
        start_time = timeit.default_timer()
        try:
            #print 'url'
            #print segment_url
            #print 'file'
            #print file_identifier
            #segment_size, segment_filename = download_segment(segment_url, file_identifier)
            now = time.time()
            elapsed = 0.0
            if lastTime != None:
                elapsed = now-lastTime
            lastTime = now
            t1 = time.time()
            segment_size, segment_filename = download_segment_efficient(segment_url, file_identifier)
            t2 = time.time()
            if elapsed != 0.0:
                procTimes.append(abs(elapsed-(t2-t1)))
            config_dash.LOG.info("{}: Downloaded segment {}".format(playback_type.upper(), segment_url))
            overall_dwn_segments += 1
        except IOError, e:
            config_dash.LOG.error("Unable to save segment %s" % e)
            return None
        segment_download_time = timeit.default_timer() - start_time
        previous_segment_times.append(segment_download_time)
        recent_download_sizes.append(segment_size)
        # Updating the JSON information
        segment_name = os.path.split(segment_url)[1]
        if "segment_info" not in config_dash.JSON_HANDLE:
            config_dash.JSON_HANDLE["segment_info"] = list()
        config_dash.JSON_HANDLE["segment_info"].append([segment_name, current_bitrate, segment_size,
                                                        segment_download_time, start_time, average_dwn_rate])
        total_downloaded += segment_size
        config_dash.LOG.info("{} : The total downloaded = {}, segment_size = {}, segment_number = {}".format(
            playback_type.upper(),
            total_downloaded, segment_size, segment_number))
        if playback_type.upper() == "SMART" and weighted_mean_object:
            weighted_mean_object.update_weighted_mean(segment_size, segment_download_time)

        segment_info = {'playback_length': video_segment_duration,
                        'size': segment_size,
                        'bitrate': current_bitrate,
                        'data': segment_filename,
                        'URI': segment_url,
                        'segment_number': segment_number}
        segment_duration = segment_info['playback_length']
        dash_player.write(segment_info)
        segment_files.append(segment_filename)
        config_dash.LOG.info("Downloaded %s. Size = %s in %s seconds" % (
            segment_url, segment_size, str(segment_download_time)))
        if previous_bitrate:
            if previous_bitrate < current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['up_shifts'] += 1
            elif previous_bitrate > current_bitrate:
                config_dash.JSON_HANDLE['playback_info']['down_shifts'] += 1
            previous_bitrate = current_bitrate

    glueConnection.stopLogging()
    glueConnection.closeConnection()

    if len(procTimes) > 0:
        config_dash.JSON_HANDLE['playback_info']['mean_proctime'] = sum(procTimes)/len(procTimes)
        config_dash.LOG.critical("Min process time {} s".format(min(procTimes)))
        config_dash.LOG.critical("Max process time {} s".format(max(procTimes)))
        config_dash.LOG.critical("Mean process time {} s".format(sum(procTimes)/len(procTimes)))
        config_dash.LOG.critical("Overall process time {} s".format(sum(procTimes)))

    # Log the mean over all measurements
    config_dash.LOG.critical("Downloaded {} segments".format(overall_dwn_segments))
    if overall_dwn_segments > 0:
        config_dash.JSON_HANDLE['playback_info']['mean_downrate'] = overall_avg_dwn_rate/(overall_dwn_segments*1000)
        config_dash.JSON_HANDLE['playback_info']['mean_downtime'] = overall_avg_dwn_time/overall_dwn_segments
        config_dash.LOG.critical("Selected mean bitrate: {} KBits".format(overall_avg_selected_rate/(overall_dwn_segments*1000)))
        config_dash.LOG.critical("Mean downrate: {} KBits".format(overall_avg_dwn_rate/(overall_dwn_segments*1000)))
        config_dash.LOG.critical("Mean download time: {} s".format(overall_avg_dwn_time/overall_dwn_segments))

    # waiting for the player to finish playing
    while dash_player.playback_state not in dash_buffer.EXIT_STATES:
        time.sleep(0.01)
    write_json()
    if not download:
        clean_files(file_identifier)


def get_segment_sizes(dp_object, segment_number):
    """ Module to get the segment sizes for the segment_number
    :param dp_object:
    :param segment_number:
    :return:
    """
    segment_sizes = dict([(bitrate, dp_object.video[bitrate].segment_sizes[segment_number]) for bitrate in dp_object.video])
    config_dash.LOG.debug("The segment sizes of {} are {}".format(segment_number, segment_sizes))
    return segment_sizes


def get_average_segment_sizes(dp_object):
    """
    Module to get the avearge segment sizes for each bitrate
    :param dp_object:
    :return: A dictionary of aveage segment sizes for each bitrate
    """
    average_segment_sizes = dict()
    for bitrate in dp_object.video:
        segment_sizes = dp_object.video[bitrate].segment_sizes
        segment_sizes = [float(i) for i in segment_sizes]
        try:
            average_segment_sizes[bitrate] = sum(segment_sizes)/len(segment_sizes)
        except ZeroDivisionError:
            average_segment_sizes[bitrate] = 0
    config_dash.LOG.info("The avearge segment size for is {}".format(average_segment_sizes.items()))
    return average_segment_sizes


def clean_files(folder_path):
    """
    :param folder_path: Local Folder to be deleted
    """
    if os.path.exists(folder_path):
        try:
            for video_file in os.listdir(folder_path):
                file_path = os.path.join(folder_path, video_file)
                if os.path.isfile(file_path):
                    os.unlink(file_path)
            os.rmdir(folder_path)
        except (WindowsError, OSError), e:
            config_dash.LOG.info("Unable to delete the folder {}. {}".format(folder_path, e))
        config_dash.LOG.info("Deleted the folder '{}' and its contents".format(folder_path))


def start_playback_all(dp_object, domain):
    """ Module that downloads the MPD-FIle and download all the representations of 
        the Module to download the MPEG-DASH media.
    """
    # audio_done_queue = Queue()
    video_done_queue = Queue()
    processes = []
    file_identifier = id_generator(6)
    config_dash.LOG.info("File Segments are in %s" % file_identifier)
    # for bitrate in dp_object.audio:
    #     # Get the list of URL's (relative location) for the audio
    #     dp_object.audio[bitrate] = read_mpd.get_url_list(bitrate, dp_object.audio[bitrate],
    #                                                      dp_object.playback_duration)
    #     # Create a new process to download the audio stream.
    #     # The domain + URL from the above list gives the
    #     # complete path
    #     # The fil-identifier is a random string used to
    #     # create  a temporary folder for current session
    #     # Audio-done queue is used to exchange information
    #     # between the process and the calling function.
    #     # 'STOP' is added to the queue to indicate the end
    #     # of the download of the sesson
    #     process = Process(target=get_media_all, args=(domain, (bitrate, dp_object.audio),
    #                                                   file_identifier, audio_done_queue))
    #     process.start()
    #     processes.append(process)

    for bitrate in dp_object.video:
        dp_object.video[bitrate] = read_mpd.get_url_list(bitrate, dp_object.video[bitrate],
                                                         dp_object.playback_duration,
                                                         dp_object.video[bitrate].segment_duration)
        # Same as download audio
        process = Process(target=get_media_all, args=(domain, (bitrate, dp_object.video),
                                                      file_identifier, video_done_queue))
        process.start()
        processes.append(process)
    for process in processes:
        process.join()
    count = 0
    for queue_values in iter(video_done_queue.get, None):
        bitrate, status, elapsed = queue_values
        if status == 'STOP':
            config_dash.LOG.critical("Completed download of %s in %f " % (bitrate, elapsed))
            count += 1
            if count == len(dp_object.video):
                # If the download of all the videos is done the stop the
                config_dash.LOG.critical("Finished download of all video segments")
                break


def create_arguments(parser):
    """ Adding arguments to the parser """
    parser.add_argument('-m', '--MPD',                   
                        help="Url to the MPD File")
    parser.add_argument('-l', '--LIST', action='store_true',
                        help="List all the representations")
    parser.add_argument('-p', '--PLAYBACK',
                        default=DEFAULT_PLAYBACK,
                        help="Playback type (basic, sara, netflix, or all)")
    parser.add_argument('-n', '--SEGMENT_LIMIT',
                        default=SEGMENT_LIMIT,
                        help="The Segment number limit")
    parser.add_argument('-d', '--DOWNLOAD', action='store_true',
                        default=False,
                        help="Keep the video files after playback")
    parser.add_argument('-q', '--QUIC', action='store_true',
                        default=False,
                        help="Use QUIC as protocol")
    parser.add_argument('-mp', '--MP', action='store_true',
                        default=False,
                        help="Activate multipath in QUIC")
    parser.add_argument('-nka', '--NO_KEEP_ALIVE', action='store_true',
                        default=False,
                        help="Keep alive connection to Server")
    parser.add_argument('-s', '--SCHEDULER',
                        default='lowRTT',
                        help="Scheduler in multipath usage (lowRTT, RR, redundant)")


def main():
    """ Main Program wrapper """
    # configure the log file
    # Create arguments
    parser = ArgumentParser(description='Process Client parameters')
    create_arguments(parser)
    args = parser.parse_args()
    globals().update(vars(args))
    configure_log_file(playback_type=PLAYBACK.lower())
    config_dash.JSON_HANDLE['playback_type'] = PLAYBACK.lower()
    if not MPD:
        print "ERROR: Please provide the URL to the MPD file. Try Again.."
        return None

    glueConnection.setupPM(QUIC, MP, not NO_KEEP_ALIVE, SCHEDULER)

    config_dash.LOG.info('Downloading MPD file %s' % MPD)
    # Retrieve the MPD files for the video
    mpd_file = get_mpd(MPD)
    domain = get_domain_name(MPD)
    dp_object = DashPlayback()
    
    # Reading the MPD file created
    dp_object, video_segment_duration = read_mpd.read_mpd(mpd_file, dp_object)
    
    config_dash.LOG.info("The DASH media has %d video representations" % len(dp_object.video))
    if LIST:
        # Print the representations and EXIT
        print_representations(dp_object)
        return None
    if "all" in PLAYBACK.lower():
        if mpd_file:
            config_dash.LOG.critical("Start ALL Parallel PLayback")
            start_playback_all(dp_object, domain)
    elif "basic" in PLAYBACK.lower():
        config_dash.LOG.critical("Started Basic-DASH Playback")
        start_playback_smart(dp_object, domain, "BASIC", DOWNLOAD, video_segment_duration)
    elif "sara" in PLAYBACK.lower():
        config_dash.LOG.critical("Started SARA-DASH Playback")
        start_playback_smart(dp_object, domain, "SMART", DOWNLOAD, video_segment_duration)
    elif "netflix" in PLAYBACK.lower():
        config_dash.LOG.critical("Started Netflix-DASH Playback")
        start_playback_smart(dp_object, domain, "NETFLIX", DOWNLOAD, video_segment_duration)
    else:
        config_dash.LOG.error("Unknown Playback parameter {}".format(PLAYBACK))
        return None

if __name__ == "__main__":
    sys.exit(main())
