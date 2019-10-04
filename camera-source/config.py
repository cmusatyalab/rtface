#!/usr/bin/env python
import os


class Config(object):
    GABRIEL_IP = os.environ.get('SERVER_IP')
    RECEIVE_FRAME = True
    VIDEO_STREAM_PORT = 9098
    RESULT_RECEIVING_PORT = 9111
    TOKEN = 1
    IMG_CLEAR_THRESHOLD = 20
    DEBUG = False
    MAX_IMAGE_WIDTH = 640
