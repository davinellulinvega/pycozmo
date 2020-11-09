#!/usr/bin/env python

import time

import pycozmo


def pycozmo_program(cli: pycozmo.client.Client):
    del cli
    while True:
        time.sleep(0.1)


pycozmo.run_program(
    pycozmo_program, enable_animations=False, log_level="DEBUG", protocol_log_level="INFO", robot_log_level="DEBUG")
