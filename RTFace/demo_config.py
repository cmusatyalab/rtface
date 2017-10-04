"""Default Configurations for RTFace.
"""


class Config(object):
    DEBUG = False
    LOG_TIME = False
    WRITE_PICTURE_DEBUG = False
    WRITE_PICTURE_DEBUG_PATH = '/tmp/RTFace_picture/'
    FACE_MAX_DRIFT_PERCENT = 0.5
    MAX_IMAGE_WIDTH = 1024
    # dlib tracking takes longer time with a large variations
    # 20ms ~ 100+ ms
    DLIB_TRACKING = True
    # whether detector should upsample
    # detection with upsample = 1 on a 640x480 image took around 200ms
    # detection with upsample = 0 on a 640x480 image took around 70ms
    DLIB_DETECTOR_UPSAMPLE_TIMES = 0
    # adjust face detector threshold, a negative number lower the threshold
    DLIB_DETECTOR_ADJUST_THRESHOLD = -0.3
    # blurry detection
    IMAGE_CLEAR_THRESHOLD = 0
    # detect
    DETECT_FRAME_INTERVAL = 20
    # an arbitrary probability for cutting of openface recognition true/false
    RECOG_PROB_THRESHOLD = 0.8
    ENCRYPT_DENATURED_REGION = False
    ENCRYPT_DENATURED_REGION_OUTPUT_PATH = 'encrypted'
    SECRET_KEY_FILE_PATH = 'secret.txt'
    PERSIST_DENATURED_IMAGE = False
    PERSIST_DENATURED_IMAGE_OUTPUT_PATH = './denatured/'
    DOWNSAMPLE_TRACKING = 1
    # frame buffer revalidation threshold
    REVALIDATION_CONF_THRESHOLD = 0.8
