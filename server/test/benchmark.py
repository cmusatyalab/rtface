#!/usr/bin/env python2
#
# Cloudlet Infrastructure for Mobile Computing
#
#   Author: Kiryong Ha <krha@cmu.edu>
#
#   Copyright (C) 2011-2013 Carnegie Mellon University
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.
#

import time
import Queue
import struct
import os
import sys
import pdb
import multiprocessing
from optparse import OptionParser
import pprint
from face_swap import FaceTransformation
from PIL import Image, ImageOps
import StringIO
import numpy as np
import json
#from scipy.ndimage import imread
import cProfile, pstats, StringIO
from NetworkProtocol import *
import cv2
import Queue
from demo_config import Config
from time import sleep
from skimage import io
import glob
from vision import *
import pickle
import operator
import yt_dataset
import dlibutils

# bad idea to transfer image back using json
class PrivacyMediatorApp(object):
    def __init__(self, transformer, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.transformer = transformer
        self.prev_timestamp = time.time()*1000

    def begin_train(self):
        self.transformer.openface_client.setTraining(True)

    def end_train(self):
        self.transformer.openface_client.setTraining(False)
        
    def train(self, rgb_img, name):
        return self.transformer.train(rgb_img, name)        
        
    def gen_response(self, response_type, value, frame=None):
        msg = {
            'type': response_type,
            'value': value,
            'time': int(time.time()*1000)
            }
        if frame != None:
            msg['frame']=base64.b64encode(frame)
            
        return json.dumps(msg)
    
    def process(self, rgb_img, bgr_img):
        # preprocessing techqniues : resize?
        face_snippets_list = self.transformer.swap_face(rgb_img, bgr_img)
        face_snippets_string = {}
        face_snippets_string['num'] = len(face_snippets_list)
        for idx, face_snippet in enumerate(face_snippets_list):
            face_snippets_string[str(idx)] = face_snippet

        result = json.dumps(face_snippets_string)
        return result

    def handle_reset(self, header_dict):
        reset = header_dict['reset']
        print 'reset openface state'            
        if reset:
            self.transformer.openface_client.reset()
            header_dict['type']=AppDataProtocol.TYPE_reset
            self.transformer.training=False
            return ""

    def handle_get_state(self, header_dict):
        get_state = header_dict['get_state']
        print 'get openface state'
        sys.stdout.flush()            
        if get_state:
            resp = self.transformer.openface_client.getState()
            header_dict['type']=AppDataProtocol.TYPE_get_state
            print 'send out response {}'.format(resp[:10])
            sys.stdout.flush()
            return str(resp)

    def handle_load_state(self, header_dict, data):
        is_load_state = header_dict['load_state']
        if is_load_state:
            sys.stdout.write('loading openface state')
            sys.stdout.write(data[:30])
            sys.stdout.flush()
            state_string = data
            self.transformer.openface_client.setState(state_string)
            header_dict['type']=AppDataProtocol.TYPE_load_state
        else:
            sys.stdout.write('error: has load_state in header, but the value is false')
        return ""

    def handle_remove_person(self, header_dict):
        print 'removing person'
        name = header_dict['remove_person']
        remove_success=False
        resp=""
        if isinstance(name, basestring):
            resp=self.transformer.openface_client.removePerson(name)
            remove_success=json.loads(resp)['val']
            print 'removing person :{} success: {}'.format(name, remove_success)
        else:
            print ('unsupported type for name of a person')
        header_dict['type']=AppDataProtocol.TYPE_remove_person
        return resp

    def handle_get_person(self, header_dict):
        sys.stdout.write('get person\n')
        sys.stdout.flush()
        is_get_person = header_dict['get_person']
        state_string=""
        if is_get_person:
            state_string = self.transformer.openface_client.getPeople()
            with open('/home/faceswap-admin/openface-state.txt','w') as f:
                f.write(state_string)
        else:
            sys.stdout.write('error: has get_person in header, but the value is false')
        header_dict['type']=AppDataProtocol.TYPE_get_person
        return str(state_string)

    def handle_add_person(self, header_dict):
        print 'adding person'
        name = header_dict['add_person']
        if isinstance(name, basestring):
            self.transformer.addPerson(name)
            self.transformer.training_cnt = 0                
            print 'training_cnt :{}'.format(self.transformer.training_cnt)
        else:
            raise TypeError('unsupported type for name of a person')
        header_dict['type']=AppDataProtocol.TYPE_add_person
        return str(name)
        
    def handle(self, header, data):
        # ! IMPORTANT !
        # python + android client sent out BGR frame
        
        # locking to make sure tracker update thread is not interrupting
        self.transformer.tracking_thread_idle_event.clear()
        
        if Config.DEBUG:
            cur_timestamp = time.time()*1000
            interval = cur_timestamp - self.prev_timestamp
            sys.stdout.write("packet interval: %d\n header: %s\n"%(interval, header))
            start = time.time()
        header_dict = header

        if 'reset' in header_dict:
            return self.handle_reset(header_dict)
        elif 'get_state' in header_dict:
            return self.handle_get_state(header_dict)
        elif 'load_state' in header_dict:
            return self.handle_load_state(header_dict,data)
        if 'remove_person' in header_dict:
            return self.handle_remove_person(header_dict)
        if 'get_person' in header_dict:
            return self.handle_get_person(header_dict)
        if 'add_person' in header_dict:
            return self.handle_add_person(header_dict)
        elif 'face_table' in header_dict:
            face_table_string = header_dict['face_table']
            print face_table_string
            face_table = json.loads(face_table_string)
            self.transformer.face_table=face_table
            for from_person, to_person in face_table.iteritems():
                print 'mapping:'
                print '{0} <-- {1}'.format(from_person, to_person)
            sys.stdout.flush()

        training = False
        if 'training' in header_dict:
            training=True
            name=header_dict['training']

        # just pixel data
        np_data=np.fromstring(data, dtype=np.uint8)
        bgr_img=cv2.imdecode(np_data,cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)        
            
        if training:
            cnt, face_json = self.transformer.train(rgb_img, name)
            header_dict['type']=AppDataProtocol.TYPE_train
            header_dict['cnt']=cnt
            header_dict['faceROI_jsons']=[]            
            if face_json is not None:
                header_dict['faceROI_jsons']=[face_json]
        else:
            # swap faces
            snippets = self.transformer.swap_face(rgb_img, bgr_img)
            header_dict['type']=AppDataProtocol.TYPE_detect
            header_dict['faceROI_jsons']=snippets

        if Config.DEBUG:
            end = time.time()
            print('total processing time: {}'.format((end-start)*1000))
            self.prev_timestamp = time.time()*1000

        self.transformer.tracking_thread_idle_event.set()

        # TODO: hacky way to wait detector to finish...
        sleep(0.04)
        return np_data.tostring()
            
        # using PIL approach to open a jpeg data
        # image_raw = Image.open(io.BytesIO(data))
        # image = np.asarray(image_raw)

        # using opencv imread to open jpeg files
        # hopefully it will hit cache but not memory
        # why not just use imdecode???
        # fake_file = '/tmp/image.jpg'
        # fh=open(fake_file,'wb')
        # fh.write(data)
        # fh.close()
        # bgr_img = cv2.imread(fake_file)
        # b,g,r = cv2.split(bgr_img)       # get b,g,r
        # image = cv2.merge([r,g,b])     # switch it to rgb

def baseline_test(transformer):        
    img_paths = glob.glob(os.path.join('samples', '*.jpg'))
    img_paths=['./samples/lennon-1.jpg']*500
    detector = dlib.get_frontal_face_detector()    
    for img_path in img_paths:
        print img_path
        rgb_img = io.imread(img_path)
        bgr_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
        # rois = detect_faces(rgb_img, detector, upsample_num_times=0, adjust_threshold=0) 
        print transformer.swap_face(rgb_img, bgr_img)            

def get_frontal_image_paths(path,det_file):
    '''
    path is the image dir
    '''
    print 'loading frontal images from {} {}'.format(path, det_file)
    num = len(glob.glob(os.path.join(path, '*.jpg')))
    img_paths=[]
    for i in range(1, num+1):
        img_path=os.path.join(path, '{}.jpg'.format(i))
        img_paths.append(img_path)
    with open(det_file, 'r') as f:
        dets=pickle.load(f)
    img_paths=[img for idx, img in enumerate(img_paths) if len(dets[idx]) > 0]
    v_dets=[det for det in dets if len(det) > 0]    
    return img_paths, v_dets

# all_people=[
# 'harsh',
# 'jeff',
# 'victor',      
# 'miho',
# 'louis',
# 'leekc',       
# 'behzad',
# 'chia',
# 'saito',
# 'ming',
# 'mushiake',    
# 'hide',
# 'fuji',
# 'joey',        
# 'james',
# 'hector',    
# 'danny',   
# 'yokoyama',
# 'rakesh',  # has less than 50 frontal images
# ]

all_people=[
'victor',      
'louis',
'behzad',
'chia',
'saito',
]

#[('rakesh', 35), ('yokoyama', 54), ('danny', 62), ('hector', 107), ('james', 117), ('joey', 125), ('fuji', 126), ('hide', 128), ('mushiake', 132), ('ming', 137), ('saito', 139), ('chia', 164), ('behzad', 172), ('leekc', 179), ('louis', 209), ('miho', 231), ('victor', 281), ('jeff', 283), ('harsh', 341)]

def bm_test(transformer):
    global all_people
    # people=[
    #     'behzad',
    #     'chia',
    #     'danny',
    #     'fuji',
    #     'harsh',
    #     'hide'
    # ]
    people=all_people
    tr_dir = './dataset/test'
    det_dir='./dataset/dets/test'    
    paths = {name:os.path.join(tr_dir, name+'.avi') for name in people}
    det_paths={name:os.path.join(det_dir, name+'.avi.pkl') for name in people}    
    print paths
    transformer.tracking_thread_idle_event.set()
    PLOG = open('performance.txt','w')
    ILOG = open('images.txt','w')    
    # add person    
    for name, path in sorted(paths.iteritems()):
        print 'performance test for {}'.format(name)
        output='./dataset/performance/fb_50/{}.pkl'.format(name)
        img_paths, v_dets=get_frontal_image_paths(path, det_paths[name])        
        print '{} has {} frontal images'.format(name, len(img_paths))
        imgs=[]
        for img_path in img_paths:
            print 'reading in {}'.format(img_path)
            imgs.append(io.imread(img_path))
            # bgr_img = cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)

        start=time.time()
        results=[]
        for i in range(0, len(imgs)):
            rgb_img=imgs[i]
            ret=transformer.swap_face(rgb_img, None)
            if ret:
                ret.frame=None
                results.append(ret)
        print 'result length {}'.format(len(results))
        end=time.time()
        sleep(5)
        results.extend(transformer.flush())
        print 'result length after flush {}'.format(len(results))
        processing_time = (end-start)*1000
        print 'time:{}'.format(processing_time)        
        with open(output, 'w+') as f:
            pickle.dump((processing_time, results), f)
        print 'finished test for {}'.format(name)
    exit(0)
        # PLOG.write(str(result) + ':')
        # PLOG.write('{:0.2f}\n'.format((time.time()-start)*1000))
        # PLOG.flush()
        # sleep(0.02)


def bm_train(transformer):
    global all_people
    people=all_people
    # people=[
        # 'behzad',
        # 'chia',
        # 'danny',
        # 'fuji',
        # 'harsh',
        # 'hide'
    # ]
    
    tr_dir = './dataset/train'
    det_dir='./dataset/dets/train'
    paths = {name:os.path.join(tr_dir, name+'.avi') for name in people}
    det_paths={name:os.path.join(det_dir, name+'.avi.pkl') for name in people}
    print paths
    tr_size=100
    tr_dict={}
    transformer.begin_train()    
    for name, path in paths.iteritems():
        # add person
        img_paths, v_dets=get_frontal_image_paths(path, det_paths[name])
        if len(img_paths) < tr_size:
            print 'training images less than {} :{}. only have {}'.format(tr_size, name, len(img_paths))
            # exit()
        print '{} has {} frontal images'.format(name, len(img_paths))
        tr_dict[name]=len(img_paths)
        # continue
    # sorted_x = sorted(tr_dict.items(), key=operator.itemgetter(1))
    # print sorted_x
        imgs=[]
        for img_path in img_paths:
            print 'reading in {}'.format(img_path)            
            imgs.append(io.imread(img_path))
            
        transformer.addPerson(name)
        transformer.training_cnt = 0
        transformer.begin_train()
        sleep(1)
        for idx, img in enumerate(imgs):
            print img_paths[idx]
            rgb_img=img
            det=v_dets[idx][0]
            transformer.bm_train(rgb_img, name, det)
            sleep(0.01)
    transformer.end_train()

def yt_train(transformer, training_sets):
    for name, training_set in training_sets.iteritems():
        transformer.addPerson(name)
        transformer.begin_train()
        for (img_path, det) in training_set[:20]:
            print 'reading in {}'.format(img_path)            
            rgb_img=io.imread(img_path)
            transformer.bm_train(rgb_img, name, det)
            sleep(0.01)
        sleep(1)
    transformer.end_train()

def yt_train_imgs(transformer, training_sets):
    for name, imgs in training_sets.iteritems():
        print 'training {}'.format(name)
        transformer.addPerson(name)
        transformer.begin_train()
        for rgb_img in imgs:
            transformer.bm_train_img(rgb_img, name)
            sleep(0.01)
        sleep(1)
    transformer.end_train()
    
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
    sleep(5)
    # with open(sys.argv[1], 'r') as f:
    #     test_sets=pickle.load(f)
    test_sets=[
        'yt/imgs/0874_02_020_jacques_chirac.avi',
        'yt/imgs/0917_03_008_jennifer_aniston.avi',
        'yt/imgs/1033_03_005_jet_li.avi',
        'yt/imgs/0845_03_015_hugh_grant.avi',
        'yt/imgs/1413_01_013_meryl_streep.avi',
        'yt/imgs/0094_03_002_al_gore.avi',
        'yt/imgs/1780_01_007_sylvester_stallone.avi',
        'yt/imgs/1762_03_004_steven_spielberg.avi',
        'yt/imgs/1195_01_009_julia_roberts.avi',
        'yt/imgs/0302_03_006_angelina_jolie.avi',
    ]
    
    if sys.argv[1] == 'test':
        output_formatter=sys.argv[2]
        for test_set in test_sets:
            yt_test_single_vid(transformer, test_set, output_formatter)
    elif sys.argv[1] == 'train':
        training_sets={}
        for video_folder in test_sets:
            name, imgs=yt_dataset.load_training_set_imgs(video_folder, 'train_imgs_from_all_other_segments')
            training_sets[name]=imgs[:20]
        yt_train_imgs(transformer, training_sets)
    
    # dummy_video_app = PrivacyMediatorApp(transformer)
    # baseline_test(transformer)
    # pdb.set_trace()
    # sleep(1000)

    
#    bm_test(transformer)


    
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
    
