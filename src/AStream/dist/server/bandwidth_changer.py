__author__ = 'pjuluri'

from random import gauss
import subprocess
import datetime
import time
import sys
# MU and sigma in Mbps
GAUSS_MU = 3 # Mbps
GAUSS_SIGMA = 0.6 # 3 * 0.2
SLEEP_TIME = 5

TC_COMMAND_TEMPLATE = "sudo bash /users/pjuluri/limit-tc-change.sh change {:.3}mbps"

def update_tc():
    next = gauss(GAUSS_MU, GAUSS_SIGMA)
    tc_command = TC_COMMAND_TEMPLATE.format(next)
    current_time = datetime.datetime.strftime(datetime.datetime.now(), '%Y-%m-%d %H:%M:%S')
    print current_time, " : ", tc_command
    sys.stdout.flush()
    tc_command = tc_command.split()
    subprocess.call(tc_command)

def run_changer(sleep_time=SLEEP_TIME):
    while True:
        time.sleep(sleep_time)
        update_tc()


if __name__ == '__main__':
    run_changer()
