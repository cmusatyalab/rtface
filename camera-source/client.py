#! /usr/bin/env python

import socket
import struct
import threading
import Queue
import StringIO
import cv2
import protocol
import json
from time import sleep
import pdb
import sys
import select
import numpy as np
from config import Config
from vision import *
from gabrielclient import *

class Controller(object):
    def __init__(self):
        super(self.__class__, self).__init__()
        self.alive=True
        self.whitelist=[]
        self.people_to_remove=[]
        self.is_training=False

        self.tokenm = tokenManager(Config.TOKEN)
        stream_cmd_q = Queue.Queue()
        result_cmd_q = Queue.Queue()    
        self.result_reply_q = Queue.Queue()
        self.video_streaming_thread=VideoStreamingThread(cmd_q=stream_cmd_q)
        stream_cmd_q.put(ClientCommand(ClientCommand.CONNECT, (Config.GABRIEL_IP, Config.VIDEO_STREAM_PORT)) )
        stream_cmd_q.put(ClientCommand(GabrielSocketCommand.STREAM, self.tokenm))    
        self.result_receiving_thread = ResultReceivingThread(cmd_q=result_cmd_q, reply_q=self.result_reply_q)    
        result_cmd_q.put(ClientCommand(ClientCommand.CONNECT, (Config.GABRIEL_IP, Config.RESULT_RECEIVING_PORT)) )
        result_cmd_q.put(ClientCommand(GabrielSocketCommand.LISTEN, self.tokenm))

        self.image_buffer=[]
        
        self.result_receiving_thread.start()
        sleep(0.1)
        self.video_streaming_thread.flags.append(VideoHeaderFlag(protocol.AppDataProtocol.TYPE_get_person, False, True))
        self.video_streaming_thread.start()

    # blocking
    def recv(self, sig_frame_available, sig_server_info_available):
        rid=0
        st=None
        try:
            while self.alive:
                resp=self.result_reply_q.get()
                # connect and send also send reply to reply queue without any data attached
                if resp.type == ClientReply.SUCCESS and resp.data is not None:
                    (resp_header, resp_data) =resp.data
                    if resp_data.startswith('dummy'):
                        print 'nothing coming out of frame revisit queue'
                        continue
                    resp_header=json.loads(resp_header)
                    if 'type' in resp_header:
                        type = resp_header['type']

                        if type == protocol.AppDataProtocol.TYPE_get_person:
                            print 'get person recv: {}'.format(resp_data)
                            state=json.loads(resp_data)
                            name_list=state['people']
                            print 'client.py name_list: {}'.format(name_list)
                            sig_server_info_available.emit(name_list)                        
                            continue
                        # ignore other type of responses for now
                        if not (type == protocol.AppDataProtocol.TYPE_train or type == protocol.AppDataProtocol.TYPE_detect):
                            continue

                        np_data=np.fromstring(resp_data, dtype=np.uint8)
                        frame=cv2.imdecode(np_data,cv2.IMREAD_COLOR)
                        height, width, _ = frame.shape
                        faceROI_jsons = resp_header['faceROI_jsons']
                        if type == 'train':
                            for faceROI_json in faceROI_jsons:
                                faceROI_dict = json.loads(faceROI_json)
                                x1 = faceROI_dict['roi_x1']
                                y1 = faceROI_dict['roi_y1']
                                x2 = faceROI_dict['roi_x2']
                                y2 = faceROI_dict['roi_y2']
                                cv2.rectangle(frame, (x1,y1), (x2, y2), (0,0,255), 1)
                                cv2.putText(frame,
                                                'train',
                                            (x1,y1),
                                                0,
                                                1,
                                                (0,0,255));

                            # display
                            rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                            sig_frame_available.emit(rgb_frame)
                                
                        else: # detect
                            # blur_rois=[]
                            # whitelist_rois=[]
                            # frontal_face_num=0
                            # for faceROI_json in faceROI_jsons:
                            #     faceROI_dict = json.loads(faceROI_json)
                            #     x1 = faceROI_dict['roi_x1']
                            #     y1 = faceROI_dict['roi_y1']
                            #     x2 = faceROI_dict['roi_x2']
                            #     y2 = faceROI_dict['roi_y2']
                            #     name = faceROI_dict['name']
                            #     if name != 'PROFILE_FACE':
                            #         frontal_face_num+=1
                                    
                            #     if name in self.whitelist:
                            #         print 'received whitelist roi {}'.format(faceROI_dict)
                            #         whitelist_rois.append((x1, y1, x2, y2))
                            #     else:
                            #         (x1, y1, x2, y2) = enlarge_roi( (x1,y1,x2,y2), 10, width, height)
                            #         blur_rois.append( (x1, y1, x2, y2) )
                                    
                            # for roi in blur_rois:
                            #     # avoid profile blurring on whitelisted faces
                            #     if not overlap_whitelist_roi(whitelist_rois, roi):
                            #         (x1, y1, x2, y2)=roi
                            #         frame[y1:y2+1, x1:x2+1]=np.resize(np.array([0]), (y2+1-y1, x2+1-x1,3))
                                    
                            # display
                            rgb_frame = cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                            if Config.DEBUG:
                                if rid % 30 == 0:
                                    if st:
                                        print 'avg FPS: {}'.format(30.0/(time.time()-st))
                                    st = time.time()
                                rid+=1

                            # # find out all images in the buffer without faces detected
                            # remove_indices=[]                            
                            # for idx, item in enumerate(self.image_buffer):
                            #     if item[1] < frontal_face_num:
                            #         remove_indices.append(idx)

                            # if len(remove_indices) > 0:
                            #     print 'new face detected. removing old images in the buffer that have fewer faces: {}'.format(remove_indices)
                            #     self.image_buffer=[v for i, v in enumerate(self.image_buffer) if i not in remove_indices]
                            # self.image_buffer.append((rgb_frame, frontal_face_num))
                            # if len(self.image_buffer) >= Config.IMAGE_BUFFER_SZ:
                            #    sig_frame_available.emit(self.image_buffer.pop(0)[0])
                            sig_frame_available.emit(rgb_frame)
                            
        except KeyboardInterrupt:
            self.video_streaming_thread.join()
            self.result_receiving_thread.join()
            with self.tokenm.has_token_cv:
                self.tokenm.has_token_cv.notifyAll()

    def start_train(self,name):
        # add person
        add_person_flag=VideoHeaderFlag(protocol.Protocol_client.JSON_KEY_ADD_PERSON, False, name)
        # mark training
        train_flag = VideoHeaderFlag(protocol.Protocol_client.JSON_KEY_TRAIN, True, name)        
        with self.video_streaming_thread.flag_lock:
            self.video_streaming_thread.flags.append(add_person_flag)            
            self.video_streaming_thread.flags.append(train_flag)
        self.is_training=True
        
    def stop_train(self):
        print 'stop train called. before lock'
        ret=None
        with self.video_streaming_thread.flag_lock:
            flag_idx=-1
            for idx, header_flag in enumerate(self.video_streaming_thread.flags):
                if header_flag.type == protocol.Protocol_client.JSON_KEY_TRAIN:
                    flag_idx = idx
                    break
            if -1 != flag_idx:
                flag = self.video_streaming_thread.flags.pop(flag_idx)
                ret = flag.data
        self.is_training=False
        return ret

    def remove_person(self, name):
        flag=VideoHeaderFlag(protocol.Protocol_client.JSON_KEY_RM_PERSON, False, name)
        with self.video_streaming_thread.flag_lock:
            self.video_streaming_thread.flags.append(flag)

    def set_whitelist(self, whitelist):
        flag=VideoHeaderFlag(protocol.Protocol_client.JSON_KEY_SET_WHITELIST, False, whitelist)
        with self.video_streaming_thread.flag_lock:
            self.video_streaming_thread.flags.append(flag)
