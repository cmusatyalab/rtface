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

import os
# must be called before dlib is set
os.environ["OMP_NUM_THREADS"] = "1"

import time
import Queue
import struct
import os
import sys
import pdb
import multiprocessing
from optparse import OptionParser
import pprint
from rtface import FaceTransformation
from PIL import Image, ImageOps
import io, StringIO
import numpy as np
import json
#from scipy.ndimage import imread
import cProfile, pstats, StringIO
from NetworkProtocol import *
import cv2
import Queue
from demo_config import Config
from vision import *
from MyUtils import create_dir, get_unused_port
import redis

GABRIELPATH = os.environ.get("GABRIELPATH")
if GABRIELPATH:
    sys.path.insert(0, os.path.join(GABRIELPATH, "server"))

import gabriel
import gabriel.proxy

logger_names = gabriel.logging.loggers
for logger_name in logger_names:
    logger = gabriel.logging.getLogger(logger_name)
    logger.setLevel(logging.WARNING)

LOG = gabriel.logging.getLogger(__name__)
dir_path = os.path.dirname(os.path.realpath(__file__))
r_server = redis.StrictRedis('localhost')
# initialize shared variables in redis
# whether there OpenFace's model needs to be updated
r_server.set('update', 0)
# clear whitelist
r_server.lrange('whitelist', 0, -1)

# move to a tool?
def process_command_line(argv):
    VERSION = 'gabriel proxy : %s' % gabriel.Const.VERSION
    DESCRIPTION = "Gabriel cognitive assistance"

    parser = OptionParser(usage='%prog [option]', version=VERSION,
            description=DESCRIPTION)

    parser.add_option(
            '-s', '--address', action='store', dest='address',
            help="(IP address:port number) of directory server")
    settings, args = parser.parse_args(argv)
    if len(args) >= 1:
        parser.error("invalid arguement")

    if hasattr(settings, 'address') and settings.address is not None:
        if settings.address.find(":") == -1:
            parser.error("Need address and port. Ex) 10.0.0.1:8081")
    return settings, args


# bad idea to transfer image back using json
class PrivacyMediatorApp(gabriel.proxy.CognitiveProcessThread):
    def __init__(self, transformer, *args, **kwargs):
        super(self.__class__, self).__init__(*args, **kwargs)
        self.transformer = transformer
        self.prev_timestamp = time.time()*1000
        self.whitelist=r_server.lrange('whitelist',0,-1)
        if Config.PERSIST_DENATURED_IMAGE:
            create_dir(Config.PERSIST_DENATURED_IMAGE_OUTPUT_PATH)

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
            name=str(name)
            if name in self.whitelist:
                self.whitelist.remove(name)
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
        elif 'set_whitelist' in header_dict:
            # remove all
            r_server.ltrim('whitelist', 1, 0)            
            for uid in header_dict['set_whitelist']:
                # add to whitelist
                r_server.rpush('whitelist', uid)
            print 'server whitelist: {}'.format(r_server.lrange('whitelist',0,-1))
            sys.stdout.flush()            

        training = False
        if 'training' in header_dict:
            training=True
            name=header_dict['training']

        # just pixel data
        np_data=np.fromstring(data, dtype=np.uint8)
        bgr_img=cv2.imdecode(np_data,cv2.IMREAD_COLOR)
        rgb_img=cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)        
#        print("prep tooks {:0.3f}".format((time.time()-start)*1000))

        if training:
            cnt, face_json = self.transformer.train(rgb_img, name)
            header_dict['type']=AppDataProtocol.TYPE_train
            header_dict['cnt']=cnt
            header_dict['faceROI_jsons']=[]            
            if face_json is not None:
                header_dict['faceROI_jsons']=[face_json]
            retval = np_data.tostring()
        else:
            # swap faces
            st=time.time()
            faceFrame, snippets = self.transformer.swap_face(rgb_img, bgr_img)
#            print("swap_face tooks {:0.3f}".format((time.time()-st)*1000))
            header_dict['type']=AppDataProtocol.TYPE_detect
            header_dict['faceROI_jsons']=[]
            if faceFrame==None:
                retval='dummy'+str(time.time())
            else:
                # need to return img, encode the image into jpeg!!
                rgb_img=faceFrame.frame
                st=time.time()
                bgr_img=cv2.cvtColor(rgb_img, cv2.COLOR_RGB2BGR)
#                print("cvtcolor tooks {:0.3f}".format((time.time()-st)*1000))

                # blur
                height, width, _ = bgr_img.shape
                blur_rois=[]                
                self.whitelist=r_server.lrange('whitelist',0,-1)
                for faceROI in faceFrame.faceROIs:
                    name = faceROI.name
                    if name in self.whitelist:
                        print('whitelisting roi {}'.format(faceROI))
                        pass
                    else:
                        faceROI.roi=clamp_roi(faceROI.roi, width, height)
                        (x1, y1, x2, y2) = enlarge_roi( faceROI.roi, 10, width, height)
                        blur_rois.append( (x1, y1, x2, y2) )

                st=time.time()
                for roi in blur_rois:
                    (x1, y1, x2, y2)=roi
                    bgr_img[y1:y2+1, x1:x2+1]=np.zeros((y2+1-y1, x2+1-x1,3))
#                print("denaturing tooks {:0.3f}".format((time.time()-st)*1000))

                st=time.time()
                _, retval=cv2.imencode('.jpg', bgr_img)

                if Config.PERSIST_DENATURED_IMAGE:
                    fname='{}'.format(time.strftime("%Y-%m-%d-%H-%M-%S.jpg"))
                    fpath=os.path.join(Config.PERSIST_DENATURED_IMAGE_OUTPUT_PATH, fname)
                    with open(fpath, 'w+') as f:
                        f.write(retval)
                retval=retval.tostring()

        if Config.DEBUG:
            self.prev_timestamp = time.time()*1000
            end = time.time()
            print('total processing time: {}'.format((end-start)*1000))
        self.transformer.tracking_thread_idle_event.set()

        # TODO: hacky way to wait detector to finish...
        # sleep(0.04)
        r_server.publish('denatured_image', retval)
        return retval
            
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

def launch_openface():
    import subprocess
    openface_port = get_unused_port()
    print "openface server listening at port: {}".format(openface_port)
    subprocess.Popen(["./openface-server/cloudlet-demo-openface-server.py",
                      "--port",
                      '{}'.format(openface_port)
                  ], cwd=dir_path)
    time.sleep(10)
    return openface_port
    
if __name__ == "__main__":
    openface_port = launch_openface()
    transformer = FaceTransformation(openface_port=openface_port)

    settings, args = process_command_line(sys.argv[1:])
    ip_addr, port = gabriel.network.get_registry_server_address(settings.address)
    service_list = gabriel.network.get_service_list(ip_addr, port)
    LOG.info("Gabriel Server :")
    LOG.info(pprint.pformat(service_list))

    video_ip = service_list.get(gabriel.ServiceMeta.VIDEO_TCP_STREAMING_IP)
    video_port = service_list.get(gabriel.ServiceMeta.VIDEO_TCP_STREAMING_PORT)
    ucomm_ip = service_list.get(gabriel.ServiceMeta.UCOMM_SERVER_IP)
    ucomm_port = service_list.get(gabriel.ServiceMeta.UCOMM_SERVER_PORT)

    # image receiving and processing threads
    image_queue = Queue.Queue(gabriel.Const.APP_LEVEL_TOKEN_SIZE)
    print "TOKEN SIZE OF OFFLOADING ENGINE: %d" % gabriel.Const.APP_LEVEL_TOKEN_SIZE # TODO
    video_receive_client = gabriel.proxy.SensorReceiveClient((video_ip, video_port), image_queue)
    video_receive_client.start()
    video_receive_client.isDaemon = True
    
    result_queue = multiprocessing.Queue()
    print result_queue._reader
    dummy_video_app = PrivacyMediatorApp(transformer, image_queue, result_queue, engine_id = 'dummy') # dummy app for image processing
    dummy_video_app.start()
    dummy_video_app.isDaemon = True

    # result publish
    result_pub = gabriel.proxy.ResultPublishClient((ucomm_ip, ucomm_port), result_queue)
    result_pub.start()
    result_pub.isDaemon = True

    try:
        while True:
            time.sleep(1)
    except Exception as e:
        pass
    except KeyboardInterrupt as e:
        sys.stdout.write("user exits\n")
    finally:
        if video_receive_client is not None:
            video_receive_client.terminate()
        if dummy_video_app is not None:
            dummy_video_app.terminate()
        if transformer is not None:
            transformer.terminate()
        result_pub.terminate()
