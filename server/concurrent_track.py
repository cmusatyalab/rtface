#!/usr/bin/python
import sys
import os
import dlib
from skimage import io
import numpy as np
import pickle
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
