#!/usr/bin/env python

import ctypes
import mmap
import os
import struct
from multiprocessing import Process, Queue, Pipe
import logging
import sys
import time
import cv2, dlib
import mmap
import shutil
import contextlib
MAPPED_FILE_PATH='/tmp/rtface'
MAPPED_FILE_SIZE= 3840 * 2160 *3
import numpy as np
import pdb

formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(processName)s %(message)s')
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
LOG.addHandler(ch)

class TrackWorker(Process):
    id = 0

    def __init__(self):
        super(TrackWorker, self).__init__()
        self.master_ip, self.worker_ip = Pipe()
        self.master_op, self.worker_op = Pipe()
        self.id = type(self).id
        type(self).id += 1

    @staticmethod
    def init_tracker(tracker, img, init_bx):
        tracker.start_track(img, init_bx)

    def clean(self):
        self.worker_ip.close()
        self.worker_op.close()
        self.master_ip.close()
        self.master_op.close()
        LOG.debug('trackWorker {} cleaned'.format(self.id))

    def __str__(self):
        return "{} idx={}".format(self.__class__.name, self.id)

    def __repr__(self):
        return "{} idx=%s".format(self.__class__.name, self.id)

    def run(self):
        raise NotImplementedError


class AsyncTrackWorker(TrackWorker):
    INIT = 'init'
    TRACK = 'track'
    KILL = 'kill'

    def __init__(self):
        super(AsyncTrackWorker, self).__init__()

    def start_track(self, img, bx):
        self.master_ip.send((self.INIT, img, bx))

    def update(self, img):
        self.master_ip.send((self.TRACK, img))

    def get_position(self):
        return self.master_op.recv()

    def clean(self):
        self.master_ip.send((self.KILL,))
        super(self.__class__, self).clean()

    def run(self):
        os.environ["OMP_NUM_THREADS"] = "1"
        LOG.debug('{} {} starts running, pid: {}'.format(self.__class__, self.id, os.getpid()))
        tracker = dlib.correlation_tracker()
        self.bx = None
        fid = 0
        while True:
            try:
                updates = self.worker_ip.recv()
            except EOFError:
                LOG.debug('EOFError! worker should have been killed before')
                break
            st = time.time()
            if updates[0] == self.INIT:
                self.init_img, self.init_bx = updates[1], updates[2]
                tracker.start_track(self.init_img, self.init_bx)
                self.bx = self.init_bx
                LOG.debug('{} {} inited at {} took: {}'.format(self, self.id, self.init_bx, time.time() - st))
            elif updates[0] == self.TRACK:
                img = updates[1]
                conf = tracker.update(img)
                self.bx = tracker.get_position()
                ret = (conf, self.bx)
                self.worker_op.send(ret)
                LOG.debug('{} {} tracked: {}'.format(self, self.id, (time.time() - st)*1000))
            elif updates[0] == self.KILL:
                tracker = None
                LOG.debug('killed: {}'.format(self))
                break
            else:
                raise ValueError('invalid action: {}'.format(updates[0]))

    def __str__(self):
        return "{} idx={}".format(self.__class__, self.id)

    def __repr__(self):
        return "{} idx=%s".format(self.__class__, self.id)

class MMapAsyncTracker(AsyncTrackWorker):

    def __init__(self):
        super(MMapAsyncTracker, self).__init__()

    def run(self):
        os.environ["OMP_NUM_THREADS"] = "1"
        LOG.debug('{} {} starts running, pid: {}'.format(self.__class__, self.id, os.getpid()))
        tracker = dlib.correlation_tracker()
        self.bx = None
        fid = 0
        tmpfile = open(MAPPED_FILE_PATH, "r")
        mf = mmap.mmap(tmpfile.fileno(), 0, access=mmap.ACCESS_READ)
        while True:
            try:
                updates = self.worker_ip.recv()
            except EOFError:
                LOG.debug('EOFError! worker should have been killed before')
                break
            st = time.time()
            if updates[0] == self.INIT:
                _, self.init_bx = updates[1], updates[2]
                self.init_img = np.fromstring(mf[:], dtype=np.uint8)
                tracker.start_track(self.init_img, self.init_bx)
                self.bx = self.init_bx
                LOG.debug('{} {} inited at {} took: {}'.format(self, self.id, self.init_bx, time.time() - st))
            elif updates[0] == self.TRACK:
                img = np.fromstring(mf[:], dtype=np.uint8)
                conf = tracker.update(img)
                self.bx = tracker.get_position()
                ret = (conf, self.bx)
                self.worker_op.send(ret)
                LOG.debug('{} {} tracked: {}'.format(self, self.id, (time.time() - st)*1000))
            elif updates[0] == self.KILL:
                tracker = None
                LOG.debug('killed: {}'.format(self))
                break
            else:
                raise ValueError('invalid action: {}'.format(updates[0]))
        mf.close()
        tmpfile.close()

def setup_mmap_file():
    tmpfile = open(MAPPED_FILE_PATH, "wb")
    tmpfile.write(MAPPED_FILE_SIZE * b'\0')
    tmpfile.close()
    tmpfile = open(MAPPED_FILE_PATH, "r+b")
    mf = mmap.mmap(tmpfile.fileno(), 0, access=mmap.ACCESS_WRITE)
    return mf



def test_mmap_worker():
    init_bx = dlib.rectangle(230, 182, 445, 397)
    cap = cv2.VideoCapture(sys.argv[1])
    mf = setup_mmap_file()
    worker = MMapAsyncTracker()
    worker.start()
    first = True
    while (True):
        # Capture frame-by-frame
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if first:
            mf[:] = frame.tostring()
            worker.start_track(None, init_bx)
            first = False
        else:
            s = time.time()
            mf[:] = frame.tostring()
            print('writing to mem mapped file took : {:0.3f}'.format((time.time() - s) * 1000))
            worker.update(None)
            conf, pos = worker.get_position()
            print('tracking time: {:0.3f}'.format((time.time() - s)*1000))

    worker.clean()
    # When everything done, release the capture
    cap.release()

def test_pipe_worker():
    init_bx = dlib.rectangle(230, 182, 445, 397)
    cap = cv2.VideoCapture(sys.argv[1])
    worker = AsyncTrackWorker()
    worker.start()
    first = True
    mf = setup_mmap_file()
    while (True):
        # Capture frame-by-frame
        ret, frame = cap.read()
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        if first:
            worker.start_track(frame, init_bx)
            first = False
        else:
            s = time.time()
            worker.update(frame)
            conf, pos = worker.get_position()
            print('tracking time: {:0.3f}'.format((time.time() - s)*1000))

    worker.clean()
    # When everything done, release the capture
    cap.release()

## Create a list to hold running Processor objects
if __name__ == "__main__":
    sys.path.append('test')
    import multiprocessing
    import logging
    mpl = multiprocessing.log_to_stderr()
    mpl.setLevel(logging.DEBUG)
    test_mmap_worker()
