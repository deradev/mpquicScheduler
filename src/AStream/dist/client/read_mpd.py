""" Module for reading the MPD file
    Author: Parikshit Juluri
    Contact : pjuluri@umkc.edu

"""
from __future__ import division
import re
import config_dash

FORMAT = 1
# Second format needs mapping bitrates->URL for each video quality.
URL_DICT = dict()
# Dictionary to convert size to bits
SIZE_DICT = {'bits':   1,
             'Kbits':  1024,
             'Mbits':  1024*1024,
             'bytes':  8,
             'KB':  1024*8,
             'MB': 1024*1024*8,
             }
# Try to import the C implementation of ElementTree which is faster
# In case of ImportError import the pure Python implementation
try:
    import xml.etree.cElementTree as ET
except ImportError:
    import xml.etree.ElementTree as ET

MEDIA_PRESENTATION_DURATION = 'mediaPresentationDuration'
MIN_BUFFER_TIME = 'minBufferTime'


def get_tag_name(xml_element):
    """ Module to remove the xmlns tag from the name
        eg: '{urn:mpeg:dash:schema:mpd:2011}SegmentTemplate'
             Return: SegmentTemplate
    """
    try:
        tag_name = xml_element[xml_element.find('}')+1:]
    except TypeError:
        config_dash.LOG.error("Unable to retrieve the tag. ")
        return None
    return tag_name


def get_playback_time(playback_duration):
    """ Get the playback time(in seconds) from the string:
        Eg: PT0H1M59.89S
    """
    # Get all the numbers in the string
    numbers = re.split('[PTHMS]', playback_duration)
    # remove all the empty strings
    numbers = [value for value in numbers if value != '']
    numbers.reverse()
    total_duration = 0
    for count, val in enumerate(numbers):
        if count == 0:
            total_duration += float(val)
        elif count == 1:
            total_duration += float(val) * 60
        elif count == 2:
            total_duration += float(val) * 60 * 60
    return total_duration


class MediaObject(object):
    """Object to handel audio and video stream """
    def __init__(self):
        self.min_buffer_time = None
        self.start = None
        self.timescale = None
        self.segment_duration = None
        self.initialization = None
        self.base_url = None
        self.url_list = list()


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


def get_url_list(media, segment_duration,  playback_duration, bitrate):
    """
    Module to get the List of URLs
    """
    if FORMAT == 0:
    # Counting the init file
        total_playback = segment_duration
        segment_count = media.start
        # Get the Base URL string
        base_url = media.base_url
        if "$Bandwidth$" in base_url:
            base_url = base_url.replace("$Bandwidth$", str(bitrate))
        if "$Number" in base_url:
            base_url = base_url.split('$')
            base_url[1] = base_url[1].replace('$', '')
            base_url[1] = base_url[1].replace('Number', '')
            base_url = ''.join(base_url)
        while True:
            media.url_list.append(base_url % segment_count)
            segment_count += 1
            if total_playback > playback_duration:
                break
            total_playback += segment_duration
    elif FORMAT == 1:
        media.url_list = URL_DICT[bitrate]
    #print media.url_list
    return media


def read_mpd(mpd_file, dashplayback):
    """ Module to read the MPD file"""
    global FORMAT
    config_dash.LOG.info("Reading the MPD file")
    try:
        tree = ET.parse(mpd_file)
    except IOError:
        config_dash.LOG.error("MPD file not found. Exiting")
        return None
    config_dash.JSON_HANDLE["video_metadata"] = {'mpd_file': mpd_file}
    root = tree.getroot()
    if 'MPD' in get_tag_name(root.tag).upper():
        if MEDIA_PRESENTATION_DURATION in root.attrib:
            dashplayback.playback_duration = get_playback_time(root.attrib[MEDIA_PRESENTATION_DURATION])
            config_dash.JSON_HANDLE["video_metadata"]['playback_duration'] = dashplayback.playback_duration
        if MIN_BUFFER_TIME in root.attrib:
            dashplayback.min_buffer_time = get_playback_time(root.attrib[MIN_BUFFER_TIME])
    format = 0;
    if "Period" in get_tag_name(root[0].tag):
        child_period = root[0]
        FORMAT = 0
    elif "Period" in get_tag_name(root[1].tag):
        child_period = root[1]
        FORMAT = 1
    #print child_period
    FORMAT = 1
    video_segment_duration = None
    if FORMAT == 0:
        for adaptation_set in child_period:

            if 'mimeType' in adaptation_set.attrib:

                media_found = False
                if 'audio' in adaptation_set.attrib['mimeType']:
                    media_object = dashplayback.audio
                    media_found = False
                    config_dash.LOG.info("Found Audio")
                elif 'video' in adaptation_set.attrib['mimeType']:
                    media_object = dashplayback.video
                    media_found = True
                    config_dash.LOG.info("Found Video")
                if media_found:
                    config_dash.LOG.info("Retrieving Media")
                    config_dash.JSON_HANDLE["video_metadata"]['available_bitrates'] = list()
                    for representation in adaptation_set:
                        bandwidth = int(representation.attrib['bandwidth'])
                        config_dash.JSON_HANDLE["video_metadata"]['available_bitrates'].append(bandwidth)
                        media_object[bandwidth] = MediaObject()
                        media_object[bandwidth].segment_sizes = []
                        for segment_info in representation:
                            if "SegmentTemplate" in get_tag_name(segment_info.tag):
                                media_object[bandwidth].base_url = segment_info.attrib['media']
                                media_object[bandwidth].start = int(segment_info.attrib['startNumber'])
                                media_object[bandwidth].timescale = float(segment_info.attrib['timescale'])
                                media_object[bandwidth].initialization = segment_info.attrib['initialization']
                            if 'video' in adaptation_set.attrib['mimeType']:
                                if "SegmentSize" in get_tag_name(segment_info.tag):
                                    try:
                                        segment_size = float(segment_info.attrib['size']) * float(
                                            SIZE_DICT[segment_info.attrib['scale']])
                                    except KeyError, e:
                                        config_dash.LOG.error("Error in reading Segment sizes :{}".format(e))
                                        continue
                                    media_object[bandwidth].segment_sizes.append(segment_size)
                                elif "SegmentTemplate" in get_tag_name(segment_info.tag):
                                    video_segment_duration = (float(segment_info.attrib['duration'])/float(
                                        segment_info.attrib['timescale']))
                                    config_dash.LOG.debug("Segment Playback Duration = {}".format(video_segment_duration))
    elif FORMAT == 1: #differentFormat

        for adaptation_set in child_period:
            for representation in adaptation_set:
                media_found = False
                if 'audio' in representation.attrib['mimeType']:
                    media_object = dashplayback.audio
                    media_found = False
                    config_dash.LOG.info("Found Audio")
                elif 'video' in representation.attrib['mimeType']:
                    media_object = dashplayback.video
                    media_found = True
                    config_dash.LOG.info("Found Video")
                if media_found:
                    config_dash.LOG.info("Retrieving Media")
                    config_dash.JSON_HANDLE["video_metadata"]['available_bitrates'] = list()
                bandwidth = int(representation.attrib['bandwidth'])
                config_dash.JSON_HANDLE["video_metadata"]['available_bitrates'].append(bandwidth)
                media_object[bandwidth] = MediaObject()
                media_object[bandwidth].segment_sizes = []
                media_object[bandwidth].start = int(representation.attrib['startWithSAP'])
                media_object[bandwidth].base_url = root[0].text
                tempcut_url = root[0].text.split('/',3)[2:]
                #cut_url = tempcut_url[1]
                cut_url = ''
                #print "cut_url = {}".format(cut_url)
                #print root[0].text
                for segment_info in representation:
                    if "SegmentBase" in get_tag_name(segment_info.tag):
                        for init in segment_info:
                            media_object[bandwidth].initialization = cut_url + init.attrib['sourceURL']

                    if 'video' in representation.attrib['mimeType']:
                        if "SegmentList" in get_tag_name(segment_info.tag):
                            for segment_URL in segment_info:
                                if "Initialization" in get_tag_name(segment_URL.tag):
                                    media_object[bandwidth].initialization = segment_URL.attrib['sourceURL']

                                elif "SegmentURL" in get_tag_name(segment_URL.tag):
                                    if video_segment_duration == None:
                                        split = segment_URL.attrib['media'].split('.')
                                        seg_dur = split[1]
                                        if len(split) > 2:
                                            seg_dur = split[1] + '.' + split[2]
                                        if seg_dur != None and len(seg_dur) > 1:
                                            seg_dur = seg_dur[1:len(seg_dur)]
                                            seg_dur = seg_dur.split('s')[0]
                                            video_segment_duration = seg_dur
                                        else:
                                            # Default segment playback time is 1 second
                                            video_segment_duration = '1'
                                    '''
                                    try:
                                        Ssize = segment_URL.attrib['media'].split('/')[0]
                                        Ssize = Ssize.split('_')[-1];
                                        Ssize = Ssize.split('kbit')[0];
                                        #print "ssize"
                                        #print Ssize
                                        segment_size = float(Ssize) * float(
                                            SIZE_DICT["Kbits"])
                                    except KeyError, e:
                                        config_dash.LOG.error("Error in reading Segment sizes :{}".format(e))
                                        continue
                                    '''
                                    segurl = cut_url + segment_URL.attrib['media']
                                    #print segurl
                                    if not bandwidth in URL_DICT.keys():
                                        URL_DICT[bandwidth] = list()
                                    URL_DICT[bandwidth].append(segurl)
                                    #media_object[bandwidth].segment_sizes.append(segment_size)



    else:

        print "Error: UknownFormat of MPD file!"

    return dashplayback, float(video_segment_duration)