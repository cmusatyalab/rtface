#!/usr/bin/env python
class Config(object):
    DEBUG=True
    WRITE_PICTURE_DEBUG=True
    WRITE_PICTURE_DEBUG_PATH='./debug_picture/'
    FACE_MAX_DRIFT_PERCENT=0.5
    MAX_IMAGE_WIDTH=1024
    # dlib tracking takes longer time with a large variations
    # 20ms ~ 100+ ms
    DLIB_TRACKING=True
    # whether detector should upsample
    # detection with upsample = 1 on a 640x480 image took around 200ms
    # detection with upsample = 0 on a 640x480 image took around 70ms
    DLIB_DETECTOR_UPSAMPLE_TIMES=0
    # adjust face detector threshold, a negative number lower the threshold
    DLIB_DETECTOR_ADJUST_THRESHOLD=-0.5

    # profile face detection
    DETECT_PROFILE_FACE=True
    # profile face cascade opencv xml path
    OPENCV_PROFILE_FACE_CASCADE_PATH='/home/faceswap-admin/dependency/dependency/opencv-src/opencv-3.1.0/data/lbpcascades/lbpcascade_profileface.xml'
