'''
Single trackers implemented using OpenCV.
They expose the same interface of start_track, update, get_position as dlib trackers

This module includes:
1. camshiftTracker
2. meanshiftTracker
'''

import numpy as np
import cv2
import dlib

from rtface.utils import LOG, drectangle_to_tuple

class camshiftTracker(object):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.selection = None
        self.hist = None
        self.track_window = None
        self.track_box = None

    def start_track(self, frame, droi):
        self.selection = drectangle_to_tuple(droi)
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, np.array((0., 60., 32.)), np.array((180., 255., 255.)))
        x0, y0, x1, y1 = self.selection
        self.track_window = (x0, y0, x1 - x0, y1 - y0)
        hsv_roi = hsv[y0:y1, x0:x1]
        mask_roi = mask[y0:y1, x0:x1]
        hist = cv2.calcHist([hsv_roi], [0], mask_roi, [16], [0, 180])
        cv2.normalize(hist, hist, 0, 255, cv2.NORM_MINMAX)
        self.hist = hist.reshape(-1)

    def update(self, frame, is_hsv=False, suggested_roi=None):
        try:
            if not is_hsv:
                hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            else:
                hsv = frame
            mask = cv2.inRange(hsv, np.array((0., 60., 32.)), np.array((180., 255., 255.)))
            prob = cv2.calcBackProject([hsv], [0], self.hist, [0, 180], 1)
            prob &= mask
            term_crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 1)
            retval, self.track_window = cv2.CamShift(prob, self.track_window, term_crit)
        except cv2.error as e:
            LOG.error('cv2 error in tracking')
            self.track_window = (0, 0, 0, 0)

    def get_position(self):
        track_rect = self.track_window
        roi_x1, roi_y1 = track_rect[0], track_rect[1]
        roi_x2 = track_rect[0] + track_rect[2]
        roi_y2 = track_rect[1] + track_rect[3]
        ret = dlib.rectangle(roi_x1, roi_y1, roi_x2, roi_y2)
        return ret

class meanshiftTracker(object):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.hist = None
        self.track_window = None
        self.track_box = None

    def start_track(self, frame, droi):
        # calculate mask
        hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
        mask = cv2.inRange(hsv, np.array((0., 60., 32.)), np.array((180., 255., 255.)))
        (x0, y0, x1, y1) = drectangle_to_tuple(droi)
        self.track_window = (x0, y0, x1 - x0, y1 - y0)
        hsv_roi = hsv[y0:y1, x0:x1]
        mask_roi = mask[y0:y1, x0:x1]
        self.hist = cv2.calcHist([hsv_roi], [0], mask_roi, [16], [0, 180])
        cv2.normalize(self.hist, self.hist, 0, 255, cv2.NORM_MINMAX)
        self.hist = self.hist.reshape(-1)

    def update(self, frame, is_hsv=False, suggested_roi=None):
        try:
            if not is_hsv:
                hsv = cv2.cvtColor(frame, cv2.COLOR_RGB2HSV)
            else:
                hsv = frame
            mask = cv2.inRange(hsv, np.array((0., 60., 32.)), np.array((180., 255., 255.)))
            prob = cv2.calcBackProject([hsv], [0], self.hist, [0, 180], 1)
            prob &= mask
            term_crit = (cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT, 10, 1)
            retval, self.track_window = cv2.meanShift(prob, self.track_window, term_crit)
        except cv2.error as e:
            LOG.error('cv2 error in tracking')
            LOG.error(e)
            self.track_window = (0, 0, 0, 0)

    def get_position(self):
        track_rect = self.track_window
        roi_x1, roi_y1 = track_rect[0], track_rect[1]
        roi_x2 = track_rect[0] + track_rect[2] - 1
        roi_y2 = track_rect[1] + track_rect[3] - 1
        ret = dlib.rectangle(roi_x1, roi_y1, roi_x2, roi_y2)
        return ret
