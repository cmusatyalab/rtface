#! /usr/bin/env python
import dlib
from vision import *
from MyUtils import *
import threading
from multiprocessing import Process, Manager
from camShift import *
from demo_config import Config

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

    def push_faceframe(self,itm):
        self.lock.acquire()
        self.cur_faces=[froi.name for froi in itm.faceROIs]
        ret=self.push(itm)
        self.lock.release()        
        # LOG.debug('items in framebuffer {}'.format(self.buf))
        # LOG.debug('framebuffer cur_faces: {}'.format(self.cur_faces))   
        return ret

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
        return True
            
            
    # def revalidate_frame(self, trackers, faceframe):
    #     frm = faceframe.frame
    #     for tracker in trackers:
    #         guess = tracker.get_position()
    #         conf=tracker.update(frm, tracker.get_position())
    #         if conf < TRACKER_CONFIDENCE_THRESHOLD:
    #             LOG.debug('frontal tracker conf too low {}'.format(conf))
    #         else:
    #             new_roi = tracker.get_position()
        
    def get_itm_idx_by_fid(self, fid):
        if self.buf:
            lowest_fid = self.buf[-1].fid
            diff = fid - lowest_fid
            return len(self.buf) - (diff+1)
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

    def has_bx(self, item, bx):
        assert(item != None)
        for faceROI in item.faceROIs:
            if iou_area(faceROI.roi, bx) > 0.5:
                return True
        return False

    @timeit
    def revalidate(self, items, bx, bxid, tracker):
        # track frames coming in earlier:
        for item in items:
            LOG.debug('revalidate fid:{}'.format(item.fid))
            if item!=None and item.frame!=None:
                if isinstance(tracker, meanshiftTracker) or isinstance(tracker, camshiftTracker):
                    tracker.update(item.frame, bx)
                elif isinstance(tracker, dlib.correlation_tracker):
                    conf=tracker.update(item.frame, bx)
                    if conf < REVALIDATION_CONF_THRESHOLD:
                        break
                else:
                    raise TypeError("unknown tracker type")
                bx=tracker.get_position()
                if self.has_bx(item, bx):
                    LOG.debug('stopped revalidation due to duplicate bx')
                    break
#                froi = FaceROI(bx, frid=bxid, name=self.cur_faces[0])
                froi = FaceROI(bx, frid=bxid, name=None)
                item.faceROIs.append(froi)
            
    def update_bx(self, fid, faces):

        if self.need_revalidate(fid, faces):
            LOG.debug('bg-thread need for revalidation')
            # update exact frame first
            for face in faces:
                bx=face.roi
                bxid=face.frid
                # race condition !!!
                self.lock.acquire()                
                mf_idx=self.get_itm_idx_by_fid(fid)
                if mf_idx > -1 and mf_idx < len(self.buf):
                    mf=self.buf[mf_idx]
                    mf.faceROIs.append(FaceROI(bx, frid=bxid))
                    LOG.debug('fid:{} --> mf_idx:{}'.format(fid,mf_idx))
                    prev_itms=self.buf[mf_idx+1:]
                    lat_itms=self.buf[:mf_idx]
                self.lock.release()                
                # make sure we can track with increasing index
                lat_itms=lat_itms[::-1]
                dbx=tuple_to_drectangle(bx)
                tracker=create_tracker(mf.frame, dbx, use_dlib=Config.DLIB_TRACKING)
#                tracker=create_tracker(mf.frame, dbx, use_dlib=False)                
                self.revalidate(prev_itms, dbx, bxid, tracker)
                tracker.start_track(mf.frame,dbx)
                self.revalidate(lat_itms, dbx, bxid, tracker)
                self.cur_faces=[froi.name for froi in self.buf[0].faceROIs]
            LOG.debug('bg-thread revalidation finished')
        else:
            LOG.debug('bg-thread no need for revalidation')

            
    def update_name(self, bxid, identity):
        self.lock.acquire()                        
        itms=self.buf[::-1]
#        itms=self.buf[::]
        LOG.debug('bg-thread update name called. current item: {}'.format(itms))
        for itm in itms:
            for froi in itm.faceROIs:
#                prev_crit = (froi.frid < bxid) and (froi.name==None)
#                post_crit=  (froi.frid > bxid) and (froi.frid <= bxid+2) and (froi.name==None)
#                help_up_crit=prev_crit or post_crit
                # if froi.frid == bxid or help_up_crit:
                if froi.frid == bxid:
                    froi.name=identity
#                    LOG.debug('bg-thread updated fid: {} to name {}'.format(itm.fid, identity))
        self.lock.release()                
                    
    def flush(self):
        self.lock.acquire()        
        self.cur_faces=[]
        ret=self.buf
        self.buf=[]
        self.lock.release()                
        return ret[::-1]
