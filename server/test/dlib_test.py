#!/usr/bin/python
import sys
sys.path.append('..')
import os
import glob
import dlib
from skimage import io
import numpy as np
import time
from collections import defaultdict
import pickle
import pdb
from vision import drectangle_to_tuple
from concurrent.futures import ProcessPoolExecutor
from dlibutils import *
from yt_dataset import *
from multiprocessing import Process, Queue, Pipe
import zmq
import json


class Processor(Process):
    def __init__(self, queue, output_queue, idx):
        super(Processor, self).__init__()
        self.queue = queue
        self.output_queue = output_queue
        self.idx = idx

    def return_name(self):
        return "Process idx=%s is called '%s'" % (self.idx, self.name)

    def run(self):
        os.environ["OMP_NUM_THREADS"] = "1"                
        tracker=dlib.correlation_tracker()        
        while True:
            updates=self.queue.get()
            ret=None
            if updates[0] == 'init':
                (img, init_bx)=updates[1]
                tracker.start_track(img, init_bx)
                ret = 'success'
            elif updates[0] == 'track':
                img=updates[1]
                tracker.update(img)
                ret = tracker.get_position()
            self.output_queue.put((self.idx, ret))

class PipeProcessor(Process):
    def __init__(self, input_p, output_p, idx):
        super(self.__class__, self).__init__()
        self.input_p = input_p
        print 'type input_p: {}'.format(type(self.input_p))
        self.output_p = output_p
        self.idx = idx

    def return_name(self):
        return "Process idx=%s is called '%s'" % (self.idx, self.name)

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
            elif updates[0] == 'track':
                img=updates[1]
                s=time.time()                
                tracker.update(img)
#                print 'tracking time: {:0.3f}'.format((time.time()-s))
                ret = tracker.get_position()
            self.output_p.send((self.idx, ret))                
#                print '{}: tracker position: {} time {:0.3f}'.format(self.idx, ret, time.time())
            
            
class zmqProcessor(Process):
    def __init__(self, idx):
        super(self.__class__, self).__init__()

        self.idx = idx

    def return_name(self):
        return "Process idx=%s is called '%s'" % (self.idx, self.name)

    def run(self):
        context = zmq.Context()        
        self.work_receiver = context.socket(zmq.SUB)
        self.work_receiver.connect("tcp://127.0.0.1:5557")
        self.work_receiver.setsockopt(zmq.SUBSCRIBE, '{}'.format(self.idx))
        tracker=dlib.correlation_tracker()        
        while True:
            print '{} waiting for recving'.format(self.idx)
            updates=self.work_receiver.recv().split()
            print 'p{} recved {} at time {:0.3f}'.format(self.idx, updates, time.time()) 
            ret=None
            if updates[1] == 'init':
                img=self.work_receiver.recv()[2:]
                img=np.fromstring(img, dtype=np.uint8)                
#                print 'p{} recved img of length {} at time {:0.3f}'.format(self.idx, img.shape, time.time())
                init_bx=self.work_receiver.recv()[2:]
                init_bx=json.loads(init_bx)
                init_bx=dlib.drectangle(*init_bx)
#                print 'p{} recved init_bx {} at time {:0.3f}'.format(self.idx, init_bx, time.time())                
                tracker.start_track(img, init_bx)
            elif updates[1] == 'track':
                img=self.work_receiver.recv()[2:]
                img=np.fromstring(img, dtype=np.uint8)
                print 'p{} recved img of length {} at time {:0.3f}'.format(self.idx, img.shape, time.time())                
                tracker.update(img)
                ret = tracker.get_position()
                print '{}: tracker position: {} time {:0.3f}'.format(self.idx, ret, time.time())
            
def sequential_track(tracker, imgs):
    for img in imgs:
        track_img(tracker, img)
    print('sequential average time {}'.format(np.average(stats['track_img'])))

# zmq is taking seconds to finish tracking
def zmq_test():
    context = zmq.Context()        
    bc = context.socket(zmq.PUB)
    bc.bind("tcp://127.0.0.1:5557")
    for i in range(0,3):
        p=zmqProcessor(idx=i)
        processes.append(p)
        p.start()

    time.sleep(2)
    for i in range(0,3):        
        print 'send at time {:0.3f}'.format(time.time())
        bc.send('{} {}'.format(i, 'init'))
        bc.send('{} {}'.format(i, imgs[0].tobytes()))
        bx=drectangle_to_tuple(init_bxes[i])
        bc.send('{} {}'.format(i, json.dumps(bx)))

    for img in imgs[1:5]:
        print 'tracking start time {:0.3f}'.format(time.time())                
        for i in range(0,3):
            bc.send('{} {}'.format(i, 'track'))
            bc.send('{} {}'.format(i, img.tobytes()))
            time.sleep(5)

def sequential_test():            
    trackers=[dlib.correlation_tracker(), dlib.correlation_tracker(), dlib.correlation_tracker()]
    for idx, tracker in enumerate(trackers):
        tracker.start_track(imgs[0], init_bxes[idx])

    s=time.time()
    for idx, tracker in enumerate(trackers):
        tracker.update(imgs[1])
        print tracker.get_position()
    print 'total time: {:0.3f}'.format((time.time()-s))

def pipe_test():
    start=time.time()            
    input_queue = [Pipe(), Pipe(), Pipe()]
    output_queue = [Pipe(), Pipe(), Pipe()]
    for i in range(0,3):
        p=PipeProcessor(input_p=input_queue[i][1], output_p=output_queue[i][1], idx=i)
        processes.append(p)
        p.start()
        input_queue[i][0].send(('init', (imgs[0], init_bxes[i])))

    for i in range(0,3):
        ret=output_queue[i][0].recv()
        print ret
    print 'total startup took :{}'.format((time.time()-start))
    
    for img in imgs[:100]:
        start=time.time()        
        for i in range(0,3):
            input_queue[i][0].send(('track',img))
        for i in range(0,3):
            ret=output_queue[i][0].recv()
        print 'took :{}'.format((time.time()-start))

def concurrent_tracker_init(img, init_bx):
    global wtracker
    wtracker=dlib.correlation_tracker()
    wtracker.start_track(img, init_bx)

def concurrent_tracker_update(img):
    wtracker.update(img)
    return tracker.get_position()
    
## Create a list to hold running Processor objects
processes = list()
if __name__ == "__main__":
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
    pipe_test()
    
    # ============== sequential test=========================
    # trackers=[dlib.correlation_tracker()]
    # for idx, tracker in enumerate(trackers):
    #     tracker.start_track(imgs[0], init_bxes[idx])

    # for img in imgs[1:]:
    #     s=time.time()        
    #     for idx, tracker in enumerate(trackers):
    #         tracker.update(img)
    #         print tracker.get_position()
    #     print 'tracking time: {:0.3f}'.format((time.time()-s))

    # ================ obsoltete ======================
    #     start=time.time()
    #     for i in range(0,3):
    #         ret=rc.recv()
    #     print 'took :{}'.format((time.time()-start))
        
    # detector=dlib.get_frontal_face_detector()
    # dets=detect_img(detector, imgs[0], upsample=1)
    # for i, d in enumerate(dets):
    #     print("Detection {}".format(d))
    

    
    # for img in imgs[:30]:
    #     start=time.time()
    #     tracker.update(img)
    #     print 'took :{}'.format((time.time()-start))
    
        
        
    # for proc in processes:
    #     proc.join()
    #     ## NOTE: You cannot depend on the results to queue / dequeue in the
    #     ## same order
    #     print "RESULT: %s" % q.get()
