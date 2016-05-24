#!/usr/bin/env python
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
import io, StringIO
import numpy as np
import json
#from scipy.ndimage import imread
import cProfile, pstats, StringIO
from NetworkProtocol import *
import cv2
import Queue
from demo_config import Config
import zmq
from time import sleep

gabriel_path=os.path.expanduser("~/gabriel-v2/gabriel/server")
if os.path.isdir(gabriel_path) is True:
    sys.path.insert(0, gabriel_path)

import gabriel
import gabriel.proxy

LOG = gabriel.logging.getLogger(__name__)
DEBUG = Config.DEBUG
prev_timestamp = time.time()*1000

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
class DummyVideoApp(gabriel.proxy.CognitiveProcessThread):

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
        # pr = cProfile.Profile()
        # pr.enable()

        # preprocessing techqniues : resize?
#        image = cv2.resize(nxt_face, dim, interpolation = cv2.INTER_AREA)

        face_snippets_list = transformer.swap_face(rgb_img, bgr_img)
        face_snippets_string = {}
        face_snippets_string['num'] = len(face_snippets_list)
        for idx, face_snippet in enumerate(face_snippets_list):
            face_snippets_string[str(idx)] = face_snippet

        result = json.dumps(face_snippets_string)
        return result

    def handle(self, header, data):
        # ! IMPORTANT !
        # python + android client sent out BGR frame
        
        # pr = cProfile.Profile()
        # pr.enable()
        
        global prev_timestamp
        global DEBUG
        global zmq_socket
        
        # locking to make sure tracker update thread is not interrupting
        transformer.tracking_thread_idle_event.clear()
        
        if Config.DEBUG:
            cur_timestamp = time.time()*1000
            interval = cur_timestamp - prev_timestamp
            sys.stdout.write("packet interval: %d\n header: %s\n"%(interval, header))
            start = time.time()
        header_dict = header

        if 'reset' in header_dict:
            reset = header_dict['reset']
            print 'reset openface state'            
            if reset:
                transformer.openface_client.reset()                
                resp=self.gen_response(AppDataProtocol.TYPE_reset, True)
                transformer.training=False
                return resp

        if 'get_state' in header_dict:
            get_state = header_dict['get_state']
            print 'get openface state'
            sys.stdout.flush()            
            if get_state:
                state_string = transformer.openface_client.getState()
                resp=self.gen_response(AppDataProtocol.TYPE_get_state, state_string)
                print 'send out response {}'.format(resp[:10])
                sys.stdout.flush()
                return resp

        if 'load_state' in header_dict:
            is_load_state = header_dict['load_state']
            if is_load_state:
                sys.stdout.write('loading openface state')
                sys.stdout.write(data[:30])
                sys.stdout.flush()
                state_string = data
                transformer.openface_client.setState(state_string)
                resp=self.gen_response(AppDataProtocol.TYPE_load_state, True)
            else:
                sys.stdout.write('error: has load_state in header, but the value is false')
                resp=self.gen_response(AppDataProtocol.TYPE_load_state, False)
            return resp
            
        if 'remove_person' in header_dict:
            print 'removing person'
            name = header_dict['remove_person']
            remove_success=False
            if isinstance(name, basestring):
                resp=transformer.openface_client.removePerson(name)
                remove_success=json.loads(resp)['val']
                print 'removing person :{} success: {}'.format(name, remove_success)
            else:
                print ('unsupported type for name of a person')
            resp=self.gen_response(AppDataProtocol.TYPE_remove_person, remove_success)
            return resp

        if 'get_person' in header_dict:
            sys.stdout.write('get person\n')
            sys.stdout.flush()
            is_get_person = header_dict['get_person']
            if is_get_person:
                state_string = transformer.openface_client.getPeople()
                resp=self.gen_response(AppDataProtocol.TYPE_get_person, state_string)
                sys.stdout.write('send out response {}\n'.format(resp))
                sys.stdout.flush()
                with open('/home/faceswap-admin/openface-state.txt','w') as f:
                    f.write(state_string)
            else:
                sys.stdout.write('error: has get_person in header, but the value is false')
                resp=self.gen_response(AppDataProtocol.TYPE_get_person, False)
            return resp
            
        if 'add_person' in header_dict:
            print 'adding person'
            name = header_dict['add_person']
            if isinstance(name, basestring):
                transformer.addPerson(name)
                transformer.training_cnt = 0                
                print 'training_cnt :{}'.format(transformer.training_cnt)
            else:
                raise TypeError('unsupported type for name of a person')
            resp=self.gen_response(AppDataProtocol.TYPE_add_person, name)
            return resp
            
        elif 'face_table' in header_dict:
            face_table_string = header_dict['face_table']
            print face_table_string
            face_table = json.loads(face_table_string)
            transformer.face_table=face_table
            for from_person, to_person in face_table.iteritems():
                print 'mapping:'
                print '{0} <-- {1}'.format(from_person, to_person)
            sys.stdout.flush()

        training = False
        if 'training' in header_dict:
            training=True
            name=header_dict['training']

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

        # just pixel data
        np_data=np.fromstring(data, dtype=np.uint8)
        bgr_img=cv2.imdecode(np_data,cv2.IMREAD_COLOR)
        rgb_img = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2RGB)        
            
        if training:
            cnt, face_json = transformer.train(rgb_img, name)
            if face_json is not None:
                msg = {
                    'num': 1,
                    'cnt': cnt,
                    '0': face_json
                }
            else:
                # time is a random number to avoid token leak
                msg = {
                    'num': 0,
                    'cnt': cnt
                }
            msg = json.dumps(msg)                
            resp= self.gen_response(AppDataProtocol.TYPE_train, msg, frame=np_data)
        else:
            # swap faces
            snippets = self.process(rgb_img, bgr_img)
            resp= self.gen_response(AppDataProtocol.TYPE_detect, snippets, frame=np_data)

        if Config.DEBUG:
            end = time.time()
            print('total processing time: {}'.format((end-start)*1000))
            prev_timestamp = time.time()*1000

        # push client image onto display queue for flask
#        sys.stdout.write('before sending out zmq packet\n')
#        zmq_socket.send(data.tostring())
#        sys.stdout.write('after sending out zmq packet\n')        
#        cv2.imwrite('frame.jpg', bgr_img)        
            
        transformer.tracking_thread_idle_event.set()

        # pr.disable()
        # s = StringIO.StringIO()
        # sortby = 'cumulative'
        # ps = pstats.Stats(pr, stream=s).sort_stats(sortby)
        # ps.print_stats()
        # print s.getvalue()
        

        # TODO: hacky way to wait detector to finish...
        sleep(0.04)
        return resp


if __name__ == "__main__":
    transformer = FaceTransformation()
#    zmq_context = zmq.Context()
#    zmq_socket=zmq_context.socket(zmq.PUSH)
#    zmq_socket.bind("ipc:///tmp/gabriel-feed")

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
    dummy_video_app = DummyVideoApp(image_queue, result_queue, engine_id = 'dummy') # dummy app for image processing
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
        if flask_process is not None and flask_process.is_alive():
            flask_process.terminate()
            flask_process.join()
        result_pub.terminate()
