#!/usr/bin/env python2

import time
import Queue
import struct
import os
import sys
import pdb
import multiprocessing
import pprint
import json
import cProfile, pstats, StringIO
import cv2
from time import sleep
from skimage import io
import glob
import pickle
import operator
import yt_dataset
import dlibutils
import dlib
import yaml
sys.path.insert(0, '..')
from proxy import PrivacyMediatorApp
from rtface import FaceTransformation
from vision import FaceROI, drectangle_to_tuple, np_array_to_jpeg_data_url

def load_imgs(img_paths):
    return [io.imread(img_path) for img_path in img_paths]

def baseline(rtface, test_dict):        
    ''' baseline pipeline test, detect and recognize every frame '''
    detector=dlib.get_frontal_face_detector()
    stats={}
    ttt=0
    ttin=0
    for nm, img_paths in test_dict.iteritems():
        print '{}:{}'.format(nm, len(img_paths))
        imgs = load_imgs(img_paths[:10])
        start=time.time()
        for fid, img in enumerate(imgs):
            ds=time.time()
            dets = dlibutils.detect_img(detector, img, upsample=1)
            print 'detect time: {}'.format(time.time() - ds)
            for det in dets:
                roi = drectangle_to_tuple(det)
                (x1,y1,x2,y2) = roi
                face_pixels = img[y1:y2+1, x1:x2+1]
                face_string = np_array_to_jpeg_data_url(face_pixels)
                rs=time.time()
                resp = rtface.openface_client.addFrame(face_string, 'detect')
                print 'recog time: {}'.format(time.time() - rs)
            print 'total time: {}'.format(time.time() - ds)
        end = time.time()
        ttt += end-start
        ttin += len(imgs) 
    stats['total_time']=ttt
    stats['num_images']=ttin
    yaml.dump(stats, open('baseline.log', 'w+'))
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

def yt_test(transformer, test_sets, output_formatter):
    transformer.tracking_thread_idle_event.set()
    for name, test_set in sorted(test_sets.iteritems()):
        print 'performance test for {}'.format(name)
        for video_folder, num_test_imgs in test_set:
            output=output_formatter.format(os.path.basename(video_folder))
            if output and os.path.isfile(output):
                continue
            img_paths=dlibutils.get_img_paths(video_folder, 0, num_test_imgs)
            print 'testing {} images from {} --> {}'.format(len(img_paths), video_folder, output)
            imgs=[]
            for img_path in img_paths:
                imgs.append(io.imread(img_path))

            results=[]
            start=time.time()            
            for i in range(0, len(imgs)):
                rgb_img=imgs[i]
                ret=transformer.swap_face(rgb_img, None)
                if ret:
                    ret.frame=None
                    results.append(ret)
            end=time.time()                    
            sleep(5)
            results.extend(transformer.flush())
            print 'result length {}'.format(len(results))            
            processing_time = (end-start)*1000
            print 'time:{}'.format(processing_time)        
            with open(output, 'w+') as f:
                pickle.dump((processing_time, results), f)
            print 'finished {}'.format(video_folder)
        print 'finished test for {}'.format(name)

def yt_test_single_vid(transformer, video_folder, output_formatter):
    output=output_formatter.format(os.path.basename(video_folder))    
    if output and os.path.isfile(output):
        return
    transformer.tracking_thread_idle_event.set()
    print 'performance test for {}'.format(video_folder)    
    img_paths=dlibutils.get_img_paths(video_folder, 0)
    print 'testing {} images from {} --> {}'.format(len(img_paths), video_folder, output)
    imgs=[]
    for img_path in img_paths:
        imgs.append(io.imread(img_path))
    
    results=[]
    start=time.time()            
    for i in range(0, len(imgs)):
        rgb_img=imgs[i]
        ret=transformer.swap_face(rgb_img, None)
        if ret:
            # ret.frame=None
            results.append(ret)
    end=time.time()                    
    sleep(10)
    results.extend(transformer.flush())
    for result in results:
        result.frame=None
    print 'result length {}'.format(len(results))            
    processing_time = (end-start)*1000
    print 'avg time:{}'.format(processing_time/len(img_paths))        
    with open(output, 'w+') as f:
        pickle.dump((processing_time, results), f)
    print 'finished {}'.format(video_folder)
        
if __name__ == "__main__":
    transformer = FaceTransformation()
    pm_app = PrivacyMediatorApp(transformer, None, None, engine_id='exp')
    sleep(2)
    if sys.argv[1] == 'baseline':
        test_dict=yt_dataset.mmsys_get_test_set()
        baseline(transformer, test_dict)
    elif sys.argv[1] == 'test':
        output_formatter=sys.argv[2]
        for test_set in test_sets:
            yt_test_single_vid(transformer, test_set, output_formatter)
    elif sys.argv[1] == 'train':
        training_set=yt_dataset.mmsys_get_training_set('yt/training_images')
        print training_set
        yt_train(transformer, training_set)

    # test_sets=[
    #     'yt/imgs/0874_02_020_jacques_chirac.avi',
    #     'yt/imgs/0917_03_008_jennifer_aniston.avi',
    #     'yt/imgs/1033_03_005_jet_li.avi',
    #     'yt/imgs/0845_03_015_hugh_grant.avi',
    #     'yt/imgs/1413_01_013_meryl_streep.avi',
    #     'yt/imgs/0094_03_002_al_gore.avi',
    #     'yt/imgs/1780_01_007_sylvester_stallone.avi',
    #     'yt/imgs/1762_03_004_steven_spielberg.avi',
    #     'yt/imgs/1195_01_009_julia_roberts.avi',
    #     'yt/imgs/0302_03_006_angelina_jolie.avi',
    # ]
    
    
    # dummy_video_app = PrivacyMediatorApp(transformer)
    # baseline_test(transformer)
    # pdb.set_trace()
    # sleep(1000)

    
#    bm_train(transformer, dummy_video_app)
#    dummy_video_app = PrivacyMediatorApp(transformer, image_queue, result_queue, engine_id = 'dummy') 
    # dummy_video_app.start()
    # dummy_video_app.isDaemon = True

    # try:
    #     while True:
    #         time.sleep(1)
    # except Exception as e:
    #     pass
    # except KeyboardInterrupt as e:
    #     sys.stdout.write("user exits\n")
    # finally:
    #     if video_receive_client is not None:
    #         video_receive_client.terminate()
    #     if dummy_video_app is not None:
    #         dummy_video_app.terminate()
    #     if transformer is not None:
    #         transformer.terminate()
    #     if flask_process is not None and flask_process.is_alive():
    #         flask_process.terminate()
    #         flask_process.join()
    #     result_pub.terminate()


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
    
