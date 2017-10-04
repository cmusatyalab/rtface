"""Frame buffer to catch missed faces.

Frame buffer temporarily stores frames to give time for revalidating missed
faces mainly due to the face detector is not triggered on every frame.
"""


from collections import defaultdict
from collections import OrderedDict
import threading

import dlib

from vision import *
import ioutil
import camShift
from demo_config import Config
from concurrent_track import BatchTrackWorker, TrackerWorkerManager


LOG = ioutil.getLogger(__name__)


class FrameBuffer(object):
    def __init__(self, sz):
        self.buf_sz = sz
        self.buf = []

    def push(self, itm):
        ret = None
        LOG.debug('buf sz: {}'.format(len(self.buf)))
        if len(self.buf) == self.buf_sz:
            ret = self.buf.pop()
            LOG.debug('pop item: {}'.format(ret))
        self.buf.insert(0, itm)
        return ret

    def revalidate(self):
        raise NotImplementedError


class FaceFrameBuffer(FrameBuffer):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.cur_faces = []
        self.lock = threading.Lock()
        self.track_man = TrackerWorkerManager()
        self.bxid_lookup_table = OrderedDict()

    @ioutil.timeit
    def update(self):
        updates = self.track_man.get()
        updates_dict = defaultdict(list)
        for (fid, bx, bxid) in updates:
            updates_dict[fid].append((bx, bxid))
        for itm in reversed(self.buf):
            if len(updates_dict[itm.fid]) > 0:
                for (bx, bxid) in updates_dict[itm.fid]:
                    # need to update names as well
                    name = None
                    if bxid in self.bxid_lookup_table:
                        name = self.bxid_lookup_table[bxid]
                    itm.faceROIs.append(FaceROI(bx, frid=bxid, name=name))

    # TODO: tmp fix, should do this in face_swap
    def fix_name(self, itm):
        if itm is not None:
            for faceROI in itm.faceROIs:
                if faceROI.frid in self.bxid_lookup_table:
                    faceROI.name = self.bxid_lookup_table[faceROI.frid]

    @ioutil.timeit
    def push_faceframe(self, itm):
        self.update()
        self.lock.acquire()
        self.cur_faces = [froi.name for froi in itm.faceROIs]
        ret = self.push(itm)
        self.lock.release()
        self.fix_name(ret)
        return ret

    def need_revalidate(self, fid, faceROIs):
        return len(faceROIs) > 0

    def get_itm_idx_by_fid(self, fid, buf):
        if buf:
            lowest_fid = buf[-1].fid
            diff = fid - lowest_fid
            return len(buf) - (diff + 1)
        else:
            return -1

    @ioutil.timeit
    def revalidate(self, items, bx, bxid, tracker):
        # track frames coming in earlier:
        for itm in items:
            LOG.debug('revalidate fid:{}'.format(itm.fid))
            if itm != None and itm.frame != None:
                if isinstance(tracker, camShift.meanshiftTracker) or isinstance(tracker, camShift.camshiftTracker):
                    tracker.update(itm.frame, bx)
                elif isinstance(tracker, dlib.correlation_tracker):
                    conf = tracker.update(itm.frame, bx)
                    if conf < Config.REVALIDATION_CONF_THRESHOLD:
                        break
                else:
                    raise TypeError("unknown tracker type")
                bx = tracker.get_position()
                if itm.has_bx(bx):
                    LOG.debug('stopped revalidation due to duplicate bx')
                    break
#                froi = FaceROI(bx, frid=bxid, name=self.cur_faces[0])
                froi = FaceROI(bx, frid=bxid, name=None)
                itm.faceROIs.append(froi)

    def snapshot(self):
        # to avoid race condition, take a snapshot of current buf
        self.lock.acquire()
        buf_snapshot = self.buf[::]
        self.lock.release()
        return buf_snapshot

    def update_bx(self, fid, backprop_faces):
        if self.need_revalidate(fid, backprop_faces):
            LOG.debug('bg-thread frq updating bx')
            buf_snapshot = self.snapshot()
            mf_idx = self.get_itm_idx_by_fid(fid, buf_snapshot)
            for face in backprop_faces:
                bx = face.roi
                bxid = face.frid
                if mf_idx > -1 and mf_idx < len(buf_snapshot):
                    mf = self.buf[mf_idx]
                    if not mf.has_bx(bx):
                        # update exact frame first
                        mf.faceROIs.append(FaceROI(bx, frid=bxid))
                        LOG.debug('fid:{} --> mf_idx:{}'.format(fid, mf_idx))
                        # split array for tracking
                        prev_itms = buf_snapshot[mf_idx + 1:]
                        lat_itms = list(reversed(buf_snapshot[:mf_idx]))
                        dbx = tuple_to_drectangle(bx)
                        if len(prev_itms) > 0:
                            twp = BatchTrackWorker(
                                mf.frame, dbx, prev_itms, bxid)
                            self.track_man.add(twp)
                        if len(lat_itms) > 0:
                            twl = BatchTrackWorker(
                                mf.frame, dbx, lat_itms, bxid)
                            self.track_man.add(twl)
                        self.cur_faces = [
                            froi.name for froi in self.buf[0].faceROIs]
            LOG.debug('bg-thread revalidation issued')
        else:
            LOG.debug('bg-thread no need for revalidation')

    def update_name(self, bxid, identity):
        self.bxid_lookup_table[bxid] = identity
        if len(self.bxid_lookup_table) > 100:
            self.bxid_lookup_table.popitem(last=False)

        self.lock.acquire()
        itms = self.buf[::-1]
        LOG.debug(
            'bg-thread update name called. bxid {} identity {} current item: {}'.format(bxid, identity, itms))
        for itm in itms:
            for froi in itm.faceROIs:
                if froi.frid == bxid:
                    froi.name = identity
        self.lock.release()

    def flush(self):
        self.lock.acquire()
        self.cur_faces = []
        ret = self.buf
        self.buf = []
        self.lock.release()
        return ret[::-1]
