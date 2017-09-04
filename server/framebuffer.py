#! /usr/bin/env python2
from collections import defaultdict

import dlib
from vision import *
from MyUtils import *
import threading
from multiprocessing import Process, Manager
from camShift import *
from demo_config import Config
from concurrent_track import BatchTrackWorker, TrackerWorkerManager
from collections import OrderedDict

REVALIDATION_CONF_THRESHOLD=0.8

class FrameBuffer(object):
    def __init__(self, sz):
        self.buf_sz=sz
        self.buf=[]

    def push(self, itm):
        ret=None
        LOG.debug('buf sz: {}'.format(len(self.buf)))
        if len(self.buf) == self.buf_sz:
            ret = self.buf.pop()
            LOG.debug('pop item: {}'.format(ret)) 
        self.buf.insert(0,itm)
        return ret

    def revalidate(self):
        raise NotImplementedError

class FaceFrameBuffer(FrameBuffer):
    def __init__(self, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.cur_faces=[]
        self.lock=threading.Lock()
        self.track_man=TrackerWorkerManager()
        self.bxid_lookup_table=OrderedDict()

    @timeit
    def update(self):
        updates=self.track_man.get()
        updates_dict=defaultdict(list)
        for (fid, bx, bxid) in updates:
            updates_dict[fid].append((bx,bxid))
        for itm in reversed(self.buf):
            if len(updates_dict[itm.fid]) > 0:
                for (bx, bxid) in updates_dict[itm.fid]:
                    # need to update names as well
                    name=None
                    if bxid in self.bxid_lookup_table:
                        name=self.bxid_lookup_table[bxid]
                    itm.faceROIs.append(FaceROI(bx, frid=bxid, name=name))

    # TODO: tmp fix, should do this in face_swap
    def fix_name(self, itm):
        if itm is not None:
            for faceROI in itm.faceROIs:
                if faceROI.frid in self.bxid_lookup_table:
                    faceROI.name=self.bxid_lookup_table[faceROI.frid]

    @timeit
    def push_faceframe(self,itm):
        self.update()
        self.lock.acquire()
        self.cur_faces=[froi.name for froi in itm.faceROIs]
        ret=self.push(itm)
        self.lock.release()        
        self.fix_name(ret)
        return ret
        # LOG.debug('items in framebuffer {}'.format(self.buf))
        # LOG.debug('framebuffer cur_faces: {}'.format(self.cur_faces))   


    # def need_revalidate(self, itm):
    #     if len(itm.faceROIs) > len(self.cur_faces):
    #         return True
    #     else:
    #         return False

    def need_revalidate(self, fid, faceROIs):
        # LOG.debug('bg-thread framebuffer cur_faces: {}'.format(self.cur_faces))
        # LOG.debug('bg-thread validation update faces {}'.format(faceROIs))
        # if (len(faceROIs) > len(self.cur_faces)):
        #     mf_idx=self.get_itm_idx_by_fid(fid)
        #     if mf_idx>0 and mf_idx<len(self.buf):
        #         return True
        #     else:
        #         LOG.debug('frame already returned! \
        #                    consider increase the size of frame buffer')
        #         return False
        # else:
        #     return False
        return len(faceROIs) > 0
            
            
    # def revalidate_frame(self, trackers, faceframe):
    #     frm = faceframe.frame
    #     for tracker in trackers:
    #         guess = tracker.get_position()
    #         conf=tracker.update(frm, tracker.get_position())
    #         if conf < TRACKER_CONFIDENCE_THRESHOLD:
    #             LOG.debug('frontal tracker conf too low {}'.format(conf))
    #         else:
    #             new_roi = tracker.get_position()
        
    def get_itm_idx_by_fid(self, fid, buf):
        if buf:
            lowest_fid = buf[-1].fid
            diff = fid - lowest_fid
            return len(buf) - (diff+1)
        else:
            return -1

    # def create_tracker_by_idx(self, fid, bx):
    #     bx=tuple_to_drectangle(bx)
    #     mf_idx=self.get_itm_idx_by_fid(fid)
    #     LOG.debug('fid:{}, mf_idx:{}, buf length:{}'.format(fid, mf_idx, len(self.buf)))
    #     return mf_idx, self.buf[mf_idx], create_tracker(self.buf[mf_idx].frame,
    #                                                     bx,
    #                                                     use_dlib=Config.DLIB_TRACKING)
        
    # def update_bx_forward(self, mf_idx, bx, bxid, tracker):
    #     # track frames coming in later
    #     for idx in range(mf_idx-1,-1,-1):
    #         LOG.debug('forward revalidating:{}'.format(idx))
    #         later_itm=self.buf[idx]
    #         tracker.update(later_itm.frame, bx)
    #         bx=tracker.get_position()
    #         froi = FaceROI(drectangle_to_tuple(bx), frid=bxid)
    #         later_itm.faceROIs.append(froi)

    # def update_bx_backward(self, mf_idx, bx, bxid, tracker):
    #     # track frames coming in earlier:
    #     for idx in range(mf_idx+1,len(self.buf)):
    #         LOG.debug('backward revalidating:{}'.format(idx))            
    #         prev_itm=self.buf[idx]
    #         conf=tracker.update(prev_itm.frame, bx)
    #         if conf < REVALIDATION_CONF_THRESHOLD:
    #             break
    #         bx=tracker.get_position()
    #         froi = FaceROI(drectangle_to_tuple(bx), frid=bxid)
    #         prev_itm.faceROIs.append(froi)

    @timeit
    def revalidate(self, items, bx, bxid, tracker):
        # track frames coming in earlier:
        for itm in items:
            LOG.debug('revalidate fid:{}'.format(itm.fid))
            if itm!=None and itm.frame!=None:
                if isinstance(tracker, meanshiftTracker) or isinstance(tracker, camshiftTracker):
                    tracker.update(itm.frame, bx)
                elif isinstance(tracker, dlib.correlation_tracker):
                    conf=tracker.update(itm.frame, bx)
                    if conf < REVALIDATION_CONF_THRESHOLD:
                        break
                else:
                    raise TypeError("unknown tracker type")
                bx=tracker.get_position()
                if itm.has_bx(bx):
                    LOG.debug('stopped revalidation due to duplicate bx')
                    break
#                froi = FaceROI(bx, frid=bxid, name=self.cur_faces[0])
                froi = FaceROI(bx, frid=bxid, name=None)
                itm.faceROIs.append(froi)

    def snapshot(self):
        # race condition !!! take a snapshot of current buf
        self.lock.acquire()
        buf_snapshot=self.buf[::]
        self.lock.release()
        return buf_snapshot

    def update_bx(self, fid, backprop_faces):
        if self.need_revalidate(fid, backprop_faces):
            LOG.debug('bg-thread frq updating bx')
            buf_snapshot=self.snapshot()
            mf_idx=self.get_itm_idx_by_fid(fid, buf_snapshot)
            for face in backprop_faces:
                bx=face.roi
                bxid=face.frid
                if mf_idx > -1 and mf_idx < len(buf_snapshot):
                    mf=self.buf[mf_idx]
                    if not mf.has_bx(bx):
                        # update exact frame first
                        mf.faceROIs.append(FaceROI(bx, frid=bxid))
                        LOG.debug('fid:{} --> mf_idx:{}'.format(fid,mf_idx))
                        # split array for tracking
                        prev_itms=buf_snapshot[mf_idx+1:]
                        lat_itms=list(reversed(buf_snapshot[:mf_idx]))
                        dbx=tuple_to_drectangle(bx)
                        if len(prev_itms) > 0:
                            twp =BatchTrackWorker(mf.frame, dbx, prev_itms, bxid)
                            self.track_man.add(twp)
                        if len(lat_itms) > 0:
                            twl =BatchTrackWorker(mf.frame, dbx, lat_itms, bxid)
                            self.track_man.add(twl)
                        self.cur_faces=[froi.name for froi in self.buf[0].faceROIs]

                        # tracker=create_tracker(mf.frame, dbx, use_dlib=Config.DLIB_TRACKING)
                        # self.revalidate(prev_itms, dbx, bxid, tracker)
                        # tracker.start_track(mf.frame,dbx)
                        # self.revalidate(lat_itms, dbx, bxid, tracker)
            LOG.debug('bg-thread revalidation issued')
        else:
            LOG.debug('bg-thread no need for revalidation')

            
    def update_name(self, bxid, identity):
        self.bxid_lookup_table[bxid] = identity
        if len(self.bxid_lookup_table) > 100:
            self.bxid_lookup_table.popitem(last=False)

        self.lock.acquire()
        itms=self.buf[::-1]
#        itms=self.buf[::]
        LOG.debug('bg-thread update name called. bxid {} identity {} current item: {}'.format(bxid, identity, itms))
        for itm in itms:
            for froi in itm.faceROIs:
                if froi.frid == bxid:
                    froi.name=identity
        self.lock.release()
#                prev_crit = (froi.frid < bxid) and (froi.name==None)
#                post_crit=  (froi.frid > bxid) and (froi.frid <= bxid+2) and (froi.name==None)
#                help_up_crit=prev_crit or post_crit
                # if froi.frid == bxid or help_up_crit:
#                    LOG.debug('bg-thread updated fid: {} to name {}'.format(itm.fid, identity))

    def flush(self):
        self.lock.acquire()        
        self.cur_faces=[]
        ret=self.buf
        self.buf=[]
        self.lock.release()                
        return ret[::-1]
