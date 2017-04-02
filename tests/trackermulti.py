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

from context import rtface
from rtface.tracker import multi
from rtface.utils import drectangle_to_tuple

class TestRtfaceMultiTracker(unittest.TestCase):
    TEST_VIDEO_PATH = 'data/test_interview.mp4'
    # label path:
    # a list of tracks
    #     317, 245, 389, 317 track
    #     485, 253, 557, 325 track
    TEST_LABEL_PATH = 'data/label.test_interview'

    def setUp(self):
        self.labels = json.load(open(self.TEST_LABEL_PATH, 'r'))
        self.truth = zip(self.labels[0], self.labels[1])

    def tearDown(self):
        pass

    def test_tracker_correctness(self):
        # for test_interview.mp4
        init_bxes = dlib.rectangles()
        init_bxes.append(dlib.rectangle(317, 245, 389, 317))
        init_bxes.append(dlib.rectangle(485, 253, 557, 325))
        tracker = multi.MMapMultiTracker(width=1280, height=720, channels=3)
        cap = cv2.VideoCapture(self.TEST_VIDEO_PATH)
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
        self.assertEqual(self.truth[1:], tracks)
        tracker.clean()
        del tracker
        cap.release()

if __name__ == "__main__":
    unittest.main()
