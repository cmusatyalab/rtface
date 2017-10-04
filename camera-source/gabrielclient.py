#! /usr/bin/env python
import socket
import struct
import threading
import Queue
import cv2
import protocol
import json
import sys
import select
import vision
import time
from socketLib import *
from config import Config

class GabrielSocketCommand(ClientCommand):
    STREAM=len(ClientCommand.ACTIONS)
    ACTIONS=ClientCommand.ACTIONS + [STREAM]
    LISTEN=len(ACTIONS)
    ACTIONS.append(LISTEN)
    
    def __init__(self, type, data=None):
        super(self.__class__.__name__, self).__init__()        

class VideoHeaderFlag(object):
    def __init__(self, type, persist, data):
        self.type = type
        self.data = data
        self.persist = persist
        
class VideoStreamingThread(SocketClientThread):
    def __init__(self, cmd_q=None, reply_q=None):
        super(self.__class__, self).__init__(cmd_q, reply_q)
        self.handlers[GabrielSocketCommand.STREAM] = self._handle_STREAM
        self.is_streaming=False
        # flags contain VideoHeaderFlag objects
        self.flags=[]
        self.flag_lock=threading.Lock()

    def run(self):
        while self.alive.isSet():
            try:
                cmd = self.cmd_q.get(True, 0.1)
                self.handlers[cmd.type](cmd)
            except Queue.Empty as e:
                continue

    def _flag(self, header):
        nxt_packet_flags=[]
        with self.flag_lock:
            while ( len(self.flags)>0 ):
                flag = self.flags.pop(0)
                header[flag.type]=flag.data
                if flag.persist:
                    nxt_packet_flags.append(flag)
            self.flags.extend(nxt_packet_flags)
                
    # tokenm: token manager
    def _handle_STREAM(self, cmd):
        tokenm = cmd.data
        self.is_streaming=True
        video_capture = cv2.VideoCapture(0)
        id=0
        while self.alive.isSet() and self.is_streaming:
            tokenm.getToken()
            ret, frame = video_capture.read()
            # threshold 50 is a very high number tolerance of blurry
            while not (vision.is_clear(frame, threshold=Config.IMG_CLEAR_THRESHOLD)):
                print 'image blurry. skip'
                time.sleep(0.015)
                ret, frame = video_capture.read()                
            h, w, _ = frame.shape
            if w > Config.MAX_IMAGE_WIDTH:
                ratio = float(Config.MAX_IMAGE_WIDTH)/w
                frame = cv2.resize(frame, (0,0), fx = ratio, fy = ratio)
            ret, jpeg_frame=cv2.imencode('.jpg', frame)
            header={protocol.Protocol_client.JSON_KEY_FRAME_ID : str(id)}
            self._flag(header)
            header_json=json.dumps(header)
            self._handle_SEND(ClientCommand(ClientCommand.SEND, header_json))
            self._handle_SEND(ClientCommand(ClientCommand.SEND, jpeg_frame.tostring()))
            id+=1
        video_capture.release()        

class ResultReceivingThread(SocketClientThread):
    def __init__(self, cmd_q=None, reply_q=None):
        super(self.__class__, self).__init__(cmd_q, reply_q)
        self.handlers[GabrielSocketCommand.LISTEN] =  self._handle_LISTEN
        self.is_listening=False
        
    def run(self):
        while self.alive.isSet():
            try:
                cmd = self.cmd_q.get(True, 0.1)
                self.handlers[cmd.type](cmd)
            except Queue.Empty as e:
                continue

    def _handle_LISTEN(self, cmd):
        tokenm = cmd.data
        self.is_listening=True
        while self.alive.isSet() and self.is_listening:
            if self.socket:
                input=[self.socket]
                inputready,outputready,exceptready = select.select(input,[],[]) 
                for s in inputready: 
                    if s == self.socket: 
                        # handle the server socket
                        header, data = self._recv_gabriel_data()
                        self.reply_q.put(self._success_reply( (header, data) ))
                        tokenm.putToken()
        
    def _recv_gabriel_data(self):
        header_size = struct.unpack("!I", self._recv_n_bytes(4))[0]
        header = self._recv_n_bytes(header_size)
        header_json = json.loads(header)
        data_size = header_json['data_size']
        data = self._recv_n_bytes(data_size)
        return (header, data)
        
# token manager implementing gabriel's token mechanism
class tokenManager(object):
    def __init__(self, token_num):
        super(self.__class__, self).__init__()        
        self.token_num=token_num
        # token val is [0..token_num)
        self.token_val=token_num -1
        self.lock = threading.Lock()
        self.has_token_cv = threading.Condition(self.lock)

    def _inc(self):
        self.token_val= (self.token_val + 1) if (self.token_val<self.token_num) else (self.token_val)

    def _dec(self):
        self.token_val= (self.token_val - 1) if (self.token_val>=0) else (self.token_val)

    def empty(self):
        return (self.token_val<0)

    def getToken(self):
        with self.has_token_cv:
            while self.token_val < 0:
                self.has_token_cv.wait()
            self._dec()

    def putToken(self):
        with self.has_token_cv:
            self._inc()                    
            if self.token_val >= 0:
                self.has_token_cv.notifyAll()
        
