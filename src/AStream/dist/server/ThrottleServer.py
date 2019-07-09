"""
Apache2 Configuration:
http://www.cyberciti.biz/faq/ubuntu-mod_python-apache-tutorial/
"""

from mod_python import apache
import time
import math
import json
import os

# File names
log_file = "/var/www/py/speed_log.txt"
json_filename = "/var/www/py/json_log.json"


test = 1
start_time = None
transfer_frequency = 30

try:
    log_handle = open(log_file, "r")
    speed_values = log_handle.readlines()
    speed_values = [int(i.strip()) for i in speed_values]
except IOError:
    log_handle = None
    speed_values = None


def read_json(json_file, read_data):
    """ Load the data from json file """
    try:
        with open(json_file, "r") as json_handle:
            json_data = json.load(json_handle)
            return json_data[read_data]
    except IOError:
        return 0

speed_position = read_json(json_filename, 'speed_position')


def get_next_rate():
    """ Return the bitrates in bytes per second
        Default = 10000 bytes per second
    """
    if speed_values:
        log_handle.seek(0)
        global speed_position
        global speed_values
        # Re-start counter if the log is completed
        if speed_position >= len(speed_values):
            speed_position = 0
        for line_number, speed in enumerate(speed_values):
            if line_number == speed_position:
                speed_position += 1
                global json_filename
                write_json(json_filename, speed_position)
                return speed
    return 10000


def handler(req):
    req.log_error('HTTP Throttle handler')
    req.send_http_header()
    if req.filename.endswith("m4s"):
        try:
            data_file = open(req.filename, 'rb')
            req.clength = os.path.getsize(req.filename)
        except IOError:
            return apache.HTTP_NOT_FOUND
        send_file_at_log_speed(req, data_file)
        data_file.close()
    else:
        req.write('<html><head><title>Testing mod_python</title></head><body>')
        global test
        req.write(str(test) + 'Hello World!!!' + req.filename)
        test += 1
        req.write('</body></html>')
    return apache.OK


def send_file_at_log_speed(req, data_file):
    """
    :param req: mp_request object
    :param data_file: file to be written to HTTP connection
    :return: HTTP Code
    """
    global start_time
    if not start_time:
        start_time = time.time()
    while True:
        t = time.time() - start_time
        speed = get_next_rate()
        prev_time = time.time()
        # Count the number of transfers the data is to be divided into
        transfers = int(math.floor(t + 1.0) * transfer_frequency - round(t * transfer_frequency))
        for _ in range(transfers):
            time.sleep(1.0/transfer_frequency)
            cur_time = time.time()
            time_diff = cur_time - prev_time
            prev_time = cur_time
            if speed != 0:
                data = data_file.read(int(speed*time_diff))
                if not len(data) == 0:
                    break
                req.write(data)
                req.flush()
        if transfers == 0:
            time.sleep(0.5/transfer_frequency)



def write_json(json_file, s_pos):
    """ Load the data from json file """
    with open(json_file, "w") as json_handle:
        json_handle.write(json.dumps({'speed_position': s_pos}))
