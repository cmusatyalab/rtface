#!/usr/bin/env python
class Config(object):
    DEBUG=True
    WRITE_PICTURE_DEBUG=True
    WRITE_PICTURE_DEBUG_PATH='./debug_picture/'
    FACE_MAX_DRIFT_PERCENT=0.5
    MAX_IMAGE_WIDTH=1024
    # dlib tracking takes longer time with a large variations
    # 20ms ~ 100+ ms
    DLIB_TRACKING=False
    # whether detector should upsample
    # detection with upsample = 1 on a 640x480 image took around 200ms
    # detection with upsample = 0 on a 640x480 image took around 70ms
    DLIB_DETECTOR_UPSAMPLE_TIMES=0
    # adjust face detector threshold, a negative number lower the threshold
    DLIB_DETECTOR_ADJUST_THRESHOLD=-0.5
