'''
A MultiTracker can simultaneously track multiple region of interests in parallel. A multitracker is built on top of
single trackers. It uses python multiprocess and different IPC schemes (python pipes, queue, mmap) to achieve
concurrent processing
'''

import ctypes
import mmap
import os
import struct
from multiprocessing import Process, Queue, Pipe
import logging
import sys
import time
import pdb

import cv2, dlib
import numpy as np

from rtface import utils

DEFAULT_MAPPED_FILE_PATH = '/tmp/rtface'
DEFAULT_MAPPED_FILE_SIZE = 3840 * 2160 * 3

formatter = logging.Formatter('%(asctime)-15s %(levelname)-8s %(processName)s %(message)s')
LOG = logging.getLogger(__name__)
LOG.setLevel(logging.DEBUG)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
LOG.addHandler(ch)


class TrackerProcessBase(Process):
    '''
    template multitracker using python pipes
    '''
    INIT = 'init'
    TRACK = 'track'
    KILL = 'kill'
    id = 0

    def __init__(self):
        '''
        set up input and output pipe to communicate with child processes
        '''
        super(TrackerProcessBase, self).__init__()
        self.master_ip, self.worker_ip = Pipe()
        self.master_op, self.worker_op = Pipe()
        self.id = type(self).id
        type(self).id += 1

    def clean(self):
        self.worker_ip.close()
        self.worker_op.close()
        self.master_ip.close()
        self.master_op.close()
        LOG.debug('trackWorker {} cleaned'.format(self.id))

    def __str__(self):
        return "{} idx={}".format(self.__class__.name, self.id)

    def __repr__(self):
        return "{} idx={}".format(self.__class__.name, self.id)

    def run(self):
        raise NotImplementedError


class PipeTrackerProcess(TrackerProcessBase):
    def __init__(self):
        super(PipeTrackerProcess, self).__init__()

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
                self.bx = utils.drectangle_to_rectangle(tracker.get_position())
                ret = (conf, self.bx)
                self.worker_op.send(ret)
                LOG.debug('{} {} tracked: {}'.format(self, self.id, (time.time() - st) * 1000))
            elif updates[0] == self.KILL:
                tracker = None
                LOG.debug('killed: {}'.format(self))
                break
            else:
                raise ValueError('invalid action: {}'.format(updates[0]))


class MMapTrackerProcess(TrackerProcessBase):
    def __init__(self, width, height, channels=3, filepath=DEFAULT_MAPPED_FILE_PATH):
        super(MMapTrackerProcess, self).__init__()
        self.filepath = filepath
        self.width = width
        self.height = height
        self.channels = channels

    def start_track(self, bx):
        self.master_ip.send((self.INIT, bx))

    def update(self):
        self.master_ip.send((self.TRACK,))

    def get_position(self):
        '''
        get position is not idempotent. should only be called once after update
        :return:
        '''
        return self.master_op.recv()

    def clean(self):
        try:
            self.master_ip.send((self.KILL,))
        except IOError as e:
            LOG.debug("pipe closed. the worker has been cleaned already")
            LOG.debug(e)
        super(self.__class__, self).clean()

    def run(self):
        os.environ["OMP_NUM_THREADS"] = "1"
        LOG.debug('{} {} starts running, pid: {}'.format(self.__class__, self.id, os.getpid()))
        tracker = dlib.correlation_tracker()
        self.bx = None
        tmpfile = open(self.filepath, "r")
        mf = mmap.mmap(tmpfile.fileno(), 0, access=mmap.ACCESS_READ)
        while True:
            try:
                updates = self.worker_ip.recv()
            except EOFError:
                LOG.debug('EOFError! worker should have been killed before')
                break
            st = time.time()
            if updates[0] == self.INIT:
                self.init_bx = updates[1]
                self.init_img = np.fromstring(mf[:], dtype=np.uint8).reshape(self.height, self.width, self.channels)
                tracker.start_track(self.init_img, self.init_bx)
                self.bx = self.init_bx
                LOG.debug('{} {} inited at {} took: {}'.format(self, self.id, self.init_bx, (time.time() - st) * 1000))
            elif updates[0] == self.TRACK:
                img = np.fromstring(mf[:], dtype=np.uint8).reshape(self.height, self.width, self.channels)
                conf = tracker.update(img)
                self.bx = utils.drectangle_to_rectangle(tracker.get_position())
                ret = (conf, self.bx)
                self.worker_op.send(ret)
                LOG.debug('{} {} took {}'.format(self, ret, (time.time() - st) * 1000))
            elif updates[0] == self.KILL:
                LOG.debug('killed: {}'.format(self))
                break
            else:
                raise ValueError('invalid action: {}'.format(updates[0]))
        mf.close()
        tmpfile.close()

    def __del__(self):
        self.clean()


class MultiTrackerBase(object):
    def __init__(self):
        super(MultiTrackerBase, self).__init__()
        self._cur_bxes = []
        self._new_result_available = False

    def start_track(self, img, bxes):
        raise NotImplementedError

    def update(self, img, guess=None):
        raise NotImplementedError

    def get_position(self):
        raise NotImplementedError


class MMapMultiTracker(MultiTrackerBase):
    def __init__(self, width, height, channels=3, filepath=DEFAULT_MAPPED_FILE_PATH):
        '''
        :param filepath: path to the file that should be memory mapped
        :param filesize: size of the memory-mapped file. It should equal to the size of input image to tracker
        '''
        super(MMapMultiTracker, self).__init__()
        self.width = width
        self.height = height
        self.channels = channels
        filesize = self.width * self.height * self.channels
        # tmpfile needs to exist before it can be memory-mapped
        self.tmpfile = open(filepath, "wb")
        self.tmpfile.write(filesize * b'\0')
        self.tmpfile.close()
        self.tmpfile = open(filepath, "r+b")
        self.mf = mmap.mmap(self.tmpfile.fileno(), 0, access=mmap.ACCESS_WRITE)
        self.workers = []

    def _resize_to(self, num):
        '''
        resize the number of workers to num
        :param num
        :return: None
        '''
        resize_count = num - len(self.workers)
        if resize_count >= 0:
            self.workers.extend(
                [MMapTrackerProcess(self.width, self.height, channels=self.channels,
                                    filepath=os.path.realpath(self.tmpfile.name)) for _ in range(resize_count)])
        else:
            map(lambda worker: worker.clean(), self.workers[resize_count:])
            del self.workers[resize_count:]
        pass

    def start_track(self, img, bxes):
        '''
        :param img: image to start tracking
        :param bxes: dlib.rectangles that contains all the boundingboxes
        :return: None
        '''
        self._resize_to(len(bxes))
        map(lambda worker: worker.start(), self.workers)
        self.mf[:] = img.tostring()
        map(lambda (worker, bx): worker.start_track(bx), zip(self.workers, bxes))

    def update(self, img, guess=None):
        self.mf[:] = img.tostring()
        map(lambda worker: worker.update(), self.workers)
        self._new_result_available = True

    def get_position(self):
        '''
        :return: tuple of tracked results
        '''
        if self._new_result_available:
            del self._cur_bxes[:]
            self._cur_bxes.extend(map(lambda worker: worker.get_position(), self.workers))
            self._new_result_available = False
        return self._cur_bxes

    def clean(self):
        self._resize_to(0)

    def __del__(self):
        self.clean()

# def setup_mmap_file():
#     tmpfile = open(MAPPED_FILE_PATH, "wb")
#     tmpfile.write(MAPPED_FILE_SIZE * b'\0')
#     tmpfile.close()
#     tmpfile = open(MAPPED_FILE_PATH, "r+b")
#     mf = mmap.mmap(tmpfile.fileno(), 0, access=mmap.ACCESS_WRITE)
#     return mf
