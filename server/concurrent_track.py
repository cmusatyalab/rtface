#!/usr/bin/python
import sys
import os
import dlib
import time
from skimage import io
from multiprocessing import Process, Queue, Pipe

class concurrentManager(object):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.c_workers=None
        # queues here are actually pipes
        self.c_input_queues=None
        self.c_output_queues=None

    def c_init(self, imgs, init_bxes):
        self.c_workers=[]
        num_worker=len(imgs)
        start=time.time()            
        self.c_input_queues = [Pipe() for i in range(num_worker)]
        self.c_output_queues = [Pipe() for i in range(num_worker)]
        for i in range(0,num_worker):
            p=PipeProcessor(input_p=self.c_input_queues[i][1],
                            output_p=self.c_output_queues[i][1],
                            idx=i)
            self.c_workers.append(p)
            p.start()
            self.c_input_queues[i][0].send(('init', (imgs[i], init_bxes[i])))
            
        ret=[]
        for i in range(0,num_worker):
            ret.append(self.c_output_queues[i][0].recv())
        print 'total startup took :{}'.format((time.time()-start))
        return ret

    def c_track(self, imgs):
        assert len(imgs) == len(self.c_workers)
        start=time.time()        
        for i in range(0, len(self.c_workers)):
            self.c_input_queues[i][0].send(('track',imgs[i]))
        ret=[]
        for i in range(0, len(self.c_workers)):
            ret.append(self.c_output_queues[i][0].recv())
        print 'c_track took :{}'.format((time.time()-start))
        return ret

    def c_kill(self):    
        for i in range(0, len(self.c_workers)):
            self.c_input_queues[i][0].send(('kill', 'now'))

class PipeProcessor(Process):
    def __init__(self, input_p, output_p, idx):
        super(self.__class__, self).__init__()
        self.input_p = input_p
        self.output_p = output_p
        self.idx = idx

    def return_name(self):
        return "Process idx=%s" % (self.idx)

    def run(self):
        os.environ["OMP_NUM_THREADS"] = "1"
        tracker=dlib.correlation_tracker()
        while True:
            updates=self.input_p.recv()
            ret=None
            if updates[0] == 'init':
                (img, init_bx)=updates[1]
                tracker.start_track(img, init_bx)
                ret = 'success'
                print 'c_worker process created: {}'.format(self.idx)
            elif updates[0] == 'track':
                img=updates[1]
                s=time.time()
                tracker.update(img)
#                print 'tracking time: {:0.3f}'.format((time.time()-s))
                ret = tracker.get_position()
            elif updates[0] == 'kill':
                print 'c_worker process killed: {}'.format(self.idx)
                break
            self.output_p.send((self.idx, ret))
#                print '{}: tracker position: {} time {:0.3f}'.format(self.idx, ret, time.time())

class TrackerWorkerManager(object):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.workers=[]

    def add(self, worker):
        self.clean()
        if worker not in self.workers:
            self.workers.append(worker)
            worker.start()

    def clean(self):
        for worker in self.workers:
            if not worker.is_alive():
                worker.clean()
        self.workers=[worker for worker in self.workers if worker.is_alive()]

    def get(self):
        updates=[]
        worker_snapshot=list(self.workers)
        for worker in worker_snapshot:
            while worker.master_op.poll():
                updates.append(worker.master_op.recv())
        return updates

class TrackWorker(Process):
    idx=0
    def __init__(self, init_img, init_bx, track_itms, bxid):
        super(self.__class__, self).__init__()
        self.master_ip, self.worker_ip=Pipe()
        self.master_op, self.worker_op=Pipe()
        self.idx = type(self).idx
        type(self).idx+=1
        self.init_img=init_img
        self.init_bx=init_bx
        self.track_itms=track_itms
        self.bxid=bxid
        assert(init_img is not None)
        assert(init_bx is not None)
        assert(track_itms is not None)
        print 'trackWorker {}, init pid: {}'.format(self.idx, os.getpid())

    def __str__(self):
        return "{} idx={} bxid:{}".format(self.__class__, self.idx, self.bxid)

    def __repr__(self):
        return "{} idx=%s bxid:{}".format(self.__class__, self.idx, self.bxid)

    @staticmethod
    def init_tracker(tracker, img, init_bx):
        tracker.start_track(img, init_bx)

    def run(self):
        st=time.time()
        print 'trackWorker {} starts running, pid: {}'.format(self.idx, os.getpid())
        os.environ["OMP_NUM_THREADS"] = "1"
        tracker=dlib.correlation_tracker()
        self.init_tracker(tracker, self.init_img, self.init_bx)
        print 'trackWorker {} inited at {} took: {}'.format(self.idx, self.init_bx, time.time()-st)
        bx=self.init_bx
        while len(self.track_itms) > 0:
            itm=self.track_itms.pop(0)
            img=itm.frame
            s=time.time()
            tracker.update(img, bx)
            print 'pid: {} tracking time: {:0.3f}'.format(os.getpid(), time.time()-s)
            bx = tracker.get_position()
            if itm.has_bx(bx):
                print '{} stopped revalidation due to duplicate bx'.format(self.idx)
                break
            self.worker_op.send((itm.fid, bx, self.bxid))
        print 'trackWorker {} took {}'.format(self.idx, time.time()-st)

    def clean(self):
        self.worker_ip.close()
        self.worker_op.close()
        self.master_ip.close()
        self.master_op.close()
        print 'trackWorker {} cleaned'.format(self.idx)

## Create a list to hold running Processor objects
if __name__ == "__main__":
    import dlibutils
    import yt_dataset
    video_folder='yt/imgs/1780_01_007_sylvester_stallone.avi'
    dets_path_prefix='yt/dets_1'
    video_name = get_yt_vid_name(video_folder)        
    img_paths = get_img_paths(video_folder, 0)
    imgs=[]
    for img_path in img_paths:
        img=io.imread(img_path)
        imgs.append(img)

    init_bxes=[dlib.rectangle(95,46,170,121),
               dlib.rectangle(194,21,237,65),
               dlib.rectangle(45,6,81,42)]

    # ============== pipe test=========================
    man=concurrentManager()
    man.c_init([imgs[0]]*3,init_bxes)
    print 'initialized!'
    
    for img in imgs[1:20]:
        poses=man.c_track([img]*3)
        print 'result: {}'.format(poses)

    man.c_kill()
