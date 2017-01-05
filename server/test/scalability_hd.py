#!/usr/bin/env python
import os
# must be called before dlib is set
os.environ["OMP_NUM_THREADS"] = "1"

import time
import Queue
import struct
import sys
import pdb
import multiprocessing
import pprint
import json
import cProfile, pstats
from cStringIO import StringIO
import cv2
from time import sleep
import glob
import pickle
import operator
import yt_dataset
import dlibutils
import dlib
import yaml
import numpy as np
from PIL import Image
from skimage import io
import objgraph
sys.path.insert(0, '..')
from proxy import PrivacyMediatorApp, launch_openface
from rtface import FaceTransformation
from vision import FaceROI, drectangle_to_tuple, np_array_to_jpeg_data_url, clamp_roi

# for obama_interview.mp4
#START_FRAME_IDX = 5000
#TEST_FRAME_NUM = 3000

# for band.mp4
START_FRAME_IDX = 0
TEST_FRAME_NUM = 2783

def load_vid(video_f, num_frames=1000):
    imgs=[]
    cap=cv2.VideoCapture(video_f)
    print 'start loading images into memory'
    while(cap.isOpened() and len(imgs)<num_frames):
        ret, frame = cap.read()
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        imgs.append(rgb_frame)
    cap.release()
    return imgs

def decode_imgs(img_paths):
    return [io.imread(img_path) for img_path in img_paths]

def decode_bulk_imgs(img_paths):
    ret=[]
    grp=[]
    for img_path in img_paths:
        grp.append(io.imread(img_path))
        if len(grp) % 100 == 0:
            ret.append(grp)
            grp=[]
    return ret
    
def load_imgs(img_paths):
    ret=[]
    for img_path in img_paths:
        with open(img_path, 'rb') as f:
            ret.append(f.read())
    return ret

def load_bulk_imgs(img_paths):
    ret=[]
    grp=[]
    for img_path in img_paths:
        with open(img_path, 'rb') as f:
            grp.append(f.read())
        if len(grp) % 100 == 0:
            ret.append(grp)
            grp=[]
    return ret

def baseline(rtface, img_paths, downsample=False, shrink_ratio=1.5):        
    ''' baseline pipeline test, detect and recognize every frame '''
    print 'start baseline test'        
    detector=dlib.get_frontal_face_detector()
    stats={}
    ttt=0
    ttp=0
    ttd=0
    ttin=0
    print 'loading images'    
    imgs = load_bulk_imgs(img_paths[START_FRAME_IDX:START_FRAME_IDX+TEST_FRAME_NUM])
    print 'running test'        
    start=time.time()
    while len(imgs) > 0:
        grp = imgs.pop(0)
        ttin += len(grp)        
        while len(grp) > 0:        
            img_raw = grp.pop(0)

            ds=time.time()
            sio = StringIO(img_raw)
            im = Image.open(sio)
            rgb_img = np.asarray(im)
            ttd += (time.time()-ds)
            
            ds=time.time()
            h, w, _ = rgb_img.shape
            if downsample:
                sm_image = cv2.resize(rgb_img, None, fx = 1.0 /shrink_ratio, fy = 1.0/shrink_ratio)
#                print 'downsample time: {}'.format(time.time() - ds)
                sm_dets = dlibutils.detect_img(detector, sm_image, upsample=0)
                dets = dlib.rectangles()
                for sm_det in sm_dets:
                    dets.append(dlib.rectangle(
                        int(sm_det.left()*shrink_ratio),
                        int(sm_det.top()*shrink_ratio),
                        int(sm_det.right()*shrink_ratio),
                        int(sm_det.bottom()*shrink_ratio),                        
                    ))
            else:
                dets = dlibutils.detect_img(detector, rgb_img, upsample=0)
#            print 'detected {} faces for time: {}'.format(len(dets), time.time() - ds) 
            for det in dets:
                roi = drectangle_to_tuple(det)
                (x1,y1,x2,y2) = clamp_roi(roi, 1080, 720)
                face_pixels = rgb_img[y1:y2+1, x1:x2+1]
                face_string = np_array_to_jpeg_data_url(face_pixels)
                rs=time.time()
                resp = rtface.openface_client.addFrame(face_string, 'detect')
            ttp += (time.time()-ds)

            im.close()
            sio.close()
            del im, sio, rgb_img
#            print 'total time: {}'.format(time.time() - ds)            
#        objgraph.show_backrefs(to)
    end = time.time()
    ttt += end-start
    stats['total_time']=ttt
    stats['processing_time']=ttp
    stats['decoding_time']=ttd
    stats['num_images']=ttin
    yaml.dump(stats, open(sys.argv[2], 'a+'))
    print 'finished!!'
    
def yt_train(transformer, training_sets):
    for name, training_set in training_sets.iteritems():
        transformer.addPerson(name)
        cnt=0
        for img_path in training_set:
            print 'reading in {}'.format(img_path)            
            rgb_img=io.imread(img_path)
            _, success=transformer.train(rgb_img, name)
            if success:
                print '{}:{}'.format(name, cnt)
                cnt+=1
            if cnt == 40:
                break
            sleep(0.01)
        sleep(1)
    transformer.openface_client.setTraining(False)

def rtface_test(transformer, img_paths):
    print 'start rtface test. logging into --> {}'.format(sys.argv[2])
    stats={}
    ttt=0
    ttp=0
    ttd=0
    ttin=0
    print 'loading images'    
#    imgs = load_imgs(img_paths[START_FRAME_IDX:START_FRAME_IDX+TEST_FRAME_NUM])
    imgs = load_bulk_imgs(img_paths[START_FRAME_IDX:START_FRAME_IDX+TEST_FRAME_NUM])
    print 'running test'        
    start=time.time()
    transformer.tracking_thread_idle_event.set()
    fid=0
    # for grp_id in range(len(imgs)):
    #     for img_raw in imgs[grp_id]:
    while len(imgs) > 0:
        grp = imgs.pop(0)
        ttin += len(grp)
        while len(grp) > 0:        
            img_raw = grp.pop(0)

            ds=time.time()
            sio = StringIO(img_raw)
            im = Image.open(sio)
            rgb_img = np.asarray(im)
            ttd += (time.time()-ds)
#            print 'decoding {:.1f}'.format((time.time()-ds)*1000)
            
            ds=time.time()
            ret, _ = transformer.swap_face(rgb_img, None)
            ttp += (time.time()-ds)

#            if ret:
#                ret.frame=None
#                ret.faceROIs=None            
            im.close()
            sio.close()
            del im, ret, sio, rgb_img
            fid+=1
        del grp
#        objgraph.show_growth(limit=10)   # Start counting
#        objgraph.show_backrefs(to)
#        objgraph.show_chain(objgraph.find_backref_chain(to,objgraph.is_proper_module))
#        print 'iter {}'.format(fid)    
#        objgraph.show_growth(limit=10)   # Start counting
#        ds=time.time()
#        objgraph.show_growth(limit=10)   # Start counting        
#        print 'total time: {}'.format(time.time() - ds)
    end = time.time()
    ttt = end-start
    stats['total_time']=ttt
    stats['processing_time']=ttp
    stats['decoding_time']=ttd
    stats['num_images']=ttin
    yaml.dump(stats, open(sys.argv[2], 'a+'))
    print 'finished'

if __name__ == "__main__":
    if not os.path.isfile(sys.argv[2]):
        raise ValueError('please specify a valid output log file')

    openface_port = launch_openface()
    transformer = FaceTransformation(openface_port=openface_port)
    pm_app = PrivacyMediatorApp(transformer, None, None, engine_id='exp')
    sleep(2)
    if sys.argv[1] == 'baseline':
        baseline(transformer, sorted(glob.glob('hd/imgs/*.jpg')))
    elif sys.argv[1] == 'downsample':
        baseline(transformer, sorted(glob.glob('hd/imgs/*.jpg')), downsample=True)
    elif sys.argv[1] == 'rtface':
        rtface_test(transformer, sorted(glob.glob('hd/imgs/*.jpg')))
    elif sys.argv[1] == 'train':
        training_set=yt_dataset.mmsys_get_training_set('hd/training_images')
        print training_set
        yt_train(transformer, training_set)

# v2    
        # 'yt/imgs/0874_02_020_jacques_chirac.avi',
        # 'yt/imgs/0917_03_008_jennifer_aniston.avi',
        # 'yt/imgs/1033_03_005_jet_li.avi',
        # 'yt/imgs/0845_03_015_hugh_grant.avi',
        # 'yt/imgs/1413_01_013_meryl_streep.avi',
        # 'yt/imgs/0094_03_002_al_gore.avi',
        # 'yt/imgs/0456_03_007_bill_clinton.avi',
        # 'yt/imgs/1762_03_004_steven_spielberg.avi',
        # 'yt/imgs/1195_01_009_julia_roberts.avi',
        # 'yt/imgs/0302_03_006_angelina_jolie.avi',
    