AStream: A rate adaptation model for DASH
==================
AStream is a Python based emulated video player to evalutae the perfomance of the DASH bitrate adaptaion algorithms.


Rate Adaptatation Algorithms Supported
--------------------------------------
1. Basic Adaptation
2. Segment Aware Rate Adaptation (SARA): Our algorithm
3. Buffer-Based Rate Adaptation (Netflix): This is based on the algorithm presented in the paper. 
   Te-Yuan Huang, Ramesh Johari, Nick McKeown, Matthew Trunnell, and Mark Watson. 2014. A buffer-based approach to rate adaptation: evidence from a large video streaming service. In Proceedings of the 2014 ACM conference on SIGCOMM (SIGCOMM '14). ACM, New York, NY, USA, 187-198. DOI=10.1145/2619239.2626296 http://doi.acm.org/10.1145/2619239.2626296

Logs
----

Buffer Logs:

1. Epoch time
2. Current Playback Time
3. Current Buffer Size (in segments)
4. Current Playback State

Playback Logs:

1. Epoch time
2. Playback time
3. Segment Number
4. Segment Size
5. Playback Bitrate 
6. Segment Size 
7. Segment Duration
8. Weighted harmonic mean average download rate

Sample Run
----------
```
python dist/client/dash_client.py -m <URL TO MPD> -p <PlaybackType> 
```

Command Line options
--------------------
```
dash_client.py [-h] [-m MPD] [-l] [-p PLAYBACK] [-n SEGMENT_LIMIT] [-d]

Process Client parameters

optional arguments:
  -h, --help            show this help message and exit
  -m MPD, --MPD MPD     Url to the MPD File
  -l, --LIST            List all the representations and quit
  -p PLAYBACK, --PLAYBACK PLAYBACK
                        Playback type ('basic', 'sara', 'netflix', or 'all')
  -n SEGMENT_LIMIT, --SEGMENT_LIMIT SEGMENT_LIMIT
                        The Segment number limit
  -d, --DOWNLOAD        Keep the video files after playback
```
