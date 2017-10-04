#!/usr/bin/env python2
#
# Copyright 2015-2016 Carnegie Mellon University
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
fileDir = os.path.dirname(os.path.realpath(__file__))
#sys.path.append(os.path.join(fileDir, "..", ".."))

import txaio
txaio.use_twisted()

from autobahn.twisted.websocket import WebSocketServerProtocol, \
    WebSocketServerFactory
from twisted.python import log
from twisted.internet import reactor, ssl

import argparse
import cv2
import imagehash
import json
from PIL import Image
import numpy as np
import os
import StringIO
import urllib
import base64

from sklearn.decomposition import PCA
from sklearn.grid_search import GridSearchCV
from sklearn.manifold import TSNE
from sklearn.svm import SVC

import matplotlib as mpl
mpl.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.cm as cm

import openface
import redis

#modelDir = os.path.join(fileDir, '..', '..', 'models')
modelDir = os.path.join(fileDir, 'models')
dlibModelDir = os.path.join(modelDir, 'dlib')
openfaceModelDir = os.path.join(modelDir, 'openface')

parser = argparse.ArgumentParser()
parser.add_argument('--dlibFacePredictor', type=str, help="Path to dlib's face predictor.",
                    default=os.path.join(dlibModelDir, "shape_predictor_68_face_landmarks.dat"))
parser.add_argument('--networkModel', type=str, help="Path to Torch network model.",
                    default=os.path.join(openfaceModelDir, 'nn4.small2.v1.t7'))
parser.add_argument('--imgDim', type=int,
                    help="Default image dimension.", default=96)
parser.add_argument('--cuda', action='store_true')
parser.add_argument('--unknown', type=bool, default=False,
                    help='Try to predict unknown people')
parser.add_argument('--port', type=int, default=9001,
                    help='WebSocket Port')

args = parser.parse_args()

align = openface.AlignDlib(args.dlibFacePredictor)
net = openface.TorchNeuralNet(args.networkModel, imgDim=args.imgDim,
                              cuda=args.cuda)

r_server = redis.StrictRedis('localhost')

class Face:

    def __init__(self, rep, identity):
        self.rep = rep
        self.identity = identity

    def __repr__(self):
        return "{{id: {}, rep[0:5]: {}}}".format(
            str(self.identity),
            self.rep[0:5]
        )


class OpenFaceServerProtocol(WebSocketServerProtocol):

    def __init__(self):
        self.images = {}
        self.people = []
        self.svm = None
        self.is_training=False
        if args.unknown:
            self.unknownImgs = np.load("./examples/web/unknown.npy")

    def onConnect(self, request):
        print("Client connecting: {0}".format(request.peer))

    def onOpen(self):
        print("WebSocket connection open.")

    def onMessage(self, payload, isBinary):
        raw = payload.decode('utf8')
        msg = json.loads(raw)
        # print("Received {} message of length {}.".format(
        #     msg['type'], len(raw)))
        if msg['type'] == "NULL":
            self.sendMessage('{"type": "NULL"}')
        elif msg['type'] == "CLEAR_TRAINING":
            print 'clear trainig'
            identity=msg['identity']
            print 'identity {}'.format(identity)
            r_server.ltrim(identity, 1, 0)
            num_reps=len(r_server.lrange(identity, 0, -1))
            print 'num samples {}'.format(num_reps)            

            trained_people=r_server.lrange('trained_people',0,-1)
            if identity in trained_people:
                r_server.lrem('trained_people',0, identity)

            r_server.set('update',1)
                
            msg={
                'type':'TRAINED',
                'NUM_SAMPLES': num_reps
            }
            self.sendMessage(json.dumps(msg))
        elif msg['type'] == "FRAME":
            self.processFrame(msg['dataURL'], msg['identity'], msg['is_training'])
            self.sendMessage('{"type": "PROCESSED"}')
        elif msg['type'] == "ADD_PERSON":
            name=msg['val'].encode('ascii', 'ignore')
            if name not in self.people:
                self.people.append(name)
            print(self.people)
        elif msg['type'] == "REMOVE_IMAGE":
            h = msg['hash'].encode('ascii', 'ignore')
            if h in self.images:
                del self.images[h]
            else:
                print("Image not found.")
        else:
            print("Warning: Unknown message type: {}".format(msg['type']))

    def onClose(self, wasClean, code, reason):
        print("WebSocket connection closed: {0}".format(reason))

    def getData(self):
        X = []
        y = []
        for img in self.images.values():
            X.append(img.rep)
            y.append(img.identity)

        numIdentities = len(set(y + [-1])) - 1
        if numIdentities == 0:
            return None

        if args.unknown:
            numUnknown = y.count(-1)
            numIdentified = len(y) - numUnknown
            numUnknownAdd = (numIdentified / numIdentities) - numUnknown
            if numUnknownAdd > 0:
                print("+ Augmenting with {} unknown images.".format(numUnknownAdd))
                for rep in self.unknownImgs[:numUnknownAdd]:
                    # print(rep)
                    X.append(rep)
                    y.append(-1)

        X = np.vstack(X)
        y = np.array(y)
        return (X, y)

    @staticmethod
    def get_img_from_url(dataURL):
        head = "data:image/jpeg;base64,"
        assert(dataURL.startswith(head))
        imgdata = base64.b64decode(dataURL[len(head):])
        imgF = StringIO.StringIO()
        imgF.write(imgdata)
        imgF.seek(0)
        img = Image.open(imgF)
        buf = np.fliplr(np.asarray(img))
        return buf

    @staticmethod
    def bgr_2_rgb(buf):
        h,w,_ = buf.shape
        rgbFrame = np.zeros((h, w, 3), dtype=np.uint8)
        rgbFrame[:, :, 0] = buf[:, :, 2]
        rgbFrame[:, :, 1] = buf[:, :, 1]
        rgbFrame[:, :, 2] = buf[:, :, 0]
        return rgbFrame

    @staticmethod
    def gen_web_img(annotatedFrame):
        plt.figure()
        plt.imshow(annotatedFrame)
        plt.xticks([])
        plt.yticks([])
        imgdata = StringIO.StringIO()
        plt.savefig(imgdata, format='png')
        imgdata.seek(0)
        content = 'data:image/png;base64,' + \
            urllib.quote(base64.b64encode(imgdata.buf))
        return content

    @staticmethod
    def plot_face(annotatedFrame, name, bb, landmarks):
        bl = (bb.left(), bb.bottom())
        tr = (bb.right(), bb.top())
        cv2.rectangle(annotatedFrame, bl, tr, color=(153, 255, 204),
                      thickness=2)
        for p in openface.AlignDlib.OUTER_EYES_AND_NOSE:
            cv2.circle(annotatedFrame, center=landmarks[p], radius=3,
                       color=(102, 204, 255), thickness=-1)
        cv2.putText(annotatedFrame, name, (bb.left(), bb.top() - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, fontScale=0.75,
                    color=(152, 255, 204), thickness=2)
        
    def processFrame(self, dataURL, identity, training):
#        print('trainig:{}'.format(training))
        buf=self.get_img_from_url(dataURL)
        rgbFrame=self.bgr_2_rgb(buf)
        
        annotatedFrame = np.copy(buf)
        bb = align.getLargestFaceBoundingBox(rgbFrame)
        if bb is not None:
            landmarks = align.findLandmarks(rgbFrame, bb)
            alignedFace = align.align(args.imgDim, rgbFrame, bb,
                                      landmarks=landmarks,
                                      landmarkIndices=openface.AlignDlib.OUTER_EYES_AND_NOSE)
            if alignedFace is not None:
                phash = str(imagehash.phash(Image.fromarray(alignedFace)))
                if phash in self.images:
                    identity = self.images[phash].identity
                else:
                    rep = net.forward(alignedFace)
                    if training:
                        self.images[phash] = Face(rep, identity)
                        content = [str(x) for x in alignedFace.flatten()]

                        trained_people=r_server.lrange('trained_people',0,-1)
                        if identity not in trained_people:
                            r_server.rpush('trained_people',identity)
                        
                        r_server.rpush(identity, rep.tolist())
                        num_reps=len(r_server.lrange(identity, 0, -1))
                        msg={
                            'type':'TRAINED',
                            'NUM_SAMPLES': num_reps
                            }
                        self.plot_face(annotatedFrame, 'training', bb, landmarks)
                        self.sendMessage(json.dumps(msg))
                    else:
                        self.plot_face(annotatedFrame, identity, bb, landmarks)

        content=self.gen_web_img(annotatedFrame)
        msg = {
            "type": "ANNOTATED",
            "content": content
        }
        plt.close()

        if self.is_training and not training:
            r_server.set('update',1)            
        self.is_training=training
        self.sendMessage(json.dumps(msg))

if __name__ == '__main__':
    log.startLogging(sys.stdout)
    cur_dir=os.path.dirname(os.path.realpath(__file__))
    contextFactory = ssl.DefaultOpenSSLContextFactory(
        "tls/domain.key",
        "tls/domain.crt"
        # os.environ.get('VIDEO_TRAINER_CERT_SECRET'),
        # os.environ.get('VIDEO_TRAINER_CERT')
    )
    # factory = WebSocketServerFactory("ws://0.0.0.0:{}".format(args.port),
    #                                  debug=False)
    factory = WebSocketServerFactory(u"wss://0.0.0.0:{}".format(args.port))
    factory.protocol = OpenFaceServerProtocol

    reactor.listenSSL(args.port, factory, contextFactory)
#    reactor.listenTCP(args.port, factory) 
    reactor.run()
