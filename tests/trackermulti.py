#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
test_rtface
----------------------------------

Tests for `rtface` module.
"""
import json
import sys
import unittest, pdb

import dlib, cv2
import time
import numpy as np

from context import rtface
from rtface.tracker import multi
from rtface.utils import drectangle_to_tuple

class TestRtfaceMultiTracker(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_tracker_correctness(self):
        TEST_VIDEO_PATH = 'data/test_interview.mp4'
        # label path:
        # a list of tracks
        #     317, 245, 389, 317 track
        #     485, 253, 557, 325 track
        TEST_LABEL_PATH = 'data/label.test_interview'
        labels = json.load(open(TEST_LABEL_PATH, 'r'))
        truth = zip(labels[0], labels[1])

        init_bxes = dlib.rectangles()
        init_bxes.append(dlib.rectangle(317, 245, 389, 317))
        init_bxes.append(dlib.rectangle(485, 253, 557, 325))
        tracker = multi.MMapMultiTracker(width=1280, height=720, channels=3)
        cap = cv2.VideoCapture(TEST_VIDEO_PATH)
        has_next_frame = True
        first_frame = True
        tracks = []
        while (True):
            has_next_frame, bgr_frame = cap.read()
            if not has_next_frame:
                break
            frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            if first_frame:
                first_frame=False
                tracker.start_track(frame, init_bxes)
            else:
                tracker.update(frame)
                trs = tracker.get_position()
                tracks.append(tuple([list(drectangle_to_tuple(bx)) for (conf, bx) in trs]))
        # compare with ground truth
        self.assertEqual(truth[1:], tracks)
        tracker.clean()
        del tracker
        cap.release()

    def _test_speed(self, video_path, tracker, init_bxes):
        cap = cv2.VideoCapture(video_path)
        has_next_frame = True
        first_frame = True
        tracks = []
        ts = []
        while (True):
            has_next_frame, bgr_frame = cap.read()
            if not has_next_frame:
                break
            frame = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
            if first_frame:
                first_frame=False
                tracker.start_track(frame, init_bxes)
            else:
                st = time.time()
                tracker.update(frame)
                trs = tracker.get_position()
                duration = 1000*(time.time()-st)
                ts.append(duration)
                # print('update took {} ms'.format(duration))
                tracks.append(tuple([list(drectangle_to_tuple(bx)) for (conf, bx) in trs]))
        print('{}x{} average tracking time {} ms'.format(tracker.width, tracker.height, np.average(ts)))
        cap.release()

    def test_2160p_speed(self):
        TEST_VIDEO_PATH = 'data/test_band2_2160p.mp4'
        # for test_interview.mp4
        init_bxes = dlib.rectangles()
        init_bxes.append(dlib.rectangle(3056, 563, 3314, 821))
        init_bxes.append(dlib.rectangle(1138, 517, 1353, 732))
        init_bxes.append(dlib.rectangle(1704, 530, 1884, 709))
        init_bxes.append(dlib.rectangle(649, 591, 907, 849))
        tracker = multi.MMapMultiTracker(width=3840, height=2160, channels=3)
        self._test_speed(TEST_VIDEO_PATH, tracker, init_bxes)
        tracker.clean()
        del tracker

    def test_1080p_speed(self):
        TEST_VIDEO_PATH = 'data/test_band2_1080p.mp4'
        # for test_interview.mp4
        init_bxes = dlib.rectangles()

        init_bxes.append(dlib.rectangle(572, 261,675, 364))
        init_bxes.append(dlib.rectangle(1529, 285,1654, 410))
        init_bxes.append(dlib.rectangle(860, 265,947, 352))
        init_bxes.append(dlib.rectangle(313, 299,437, 423))
        tracker = multi.MMapMultiTracker(width=1920, height=1080, channels=3)
        self._test_speed(TEST_VIDEO_PATH, tracker, init_bxes)
        tracker.clean()
        del tracker

if __name__ == "__main__":
    unittest.main()
