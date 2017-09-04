#!/usr/bin/env python2
from flask import Flask, request, render_template, session, redirect, url_for, flash, send_from_directory, send_file, Response
from flask.ext.bootstrap import Bootstrap
from openfaceClient import OpenFaceClient, AsyncOpenFaceClientProcess

from flask import Flask
import json
import zmq
import sys

app = Flask(__name__)
bootstrap = Bootstrap(app)

server_ip = u"ws://localhost"
server_port = 9000

# communication with zmq gabriel-feed
context = zmq.Context()
zmq_socket = context.socket(zmq.PULL)
zmq_socket.connect("ipc:///tmp/gabriel-feed")
#zmq_socket.connect("tcp://127.0.0.1:20010")


@app.route('/blur', methods=['POST'])
def blur():
    people = request.form.getlist('checkbox')
    print 'blurring people : {}'.format(people)
    with open('/home/faceswap-admin/blur-list.txt', 'w') as f:
        json.dump(people, f)
    
    return redirect(url_for('index'))            

@app.route('/image/frame.jpg')
def send_image():
    return send_file('/home/faceswap-admin/privacy-mediator/image/frame.jpg')
#    return send_from_directory('image', path)    

@app.route('/whitelist', methods=['GET'])
def whitelist():
    with open('/home/faceswap-admin/openface-state.txt', 'r') as f:
        data=f.read()
        data_json = json.loads(data)
        people=data_json['people']
        people = [str(person) for person in people]
    return render_template('index.html', people=people)        

# class Camera(object):
#     def __init__(self):
#         self.frames = [open(f + '.jpg', 'rb').read() for f in ['1', '2', '3']]
        
#     def get_frame(self):
#         return self.frames[int(time()) % 3]
        
#     def set_frame(self):
#         global client_image_queue
#         client_image_queue.put(self.frames[int(time()) % 3])

@app.route('/')
def index():
    """Video streaming home page."""
    return render_template('index.html')

def debug_gen(camera):
    """Video streaming generator function."""
    while True:
        camera.set_frame()
        frame=client_image_queue.get()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

def gen():
    """Video streaming generator function."""
    while True:
        frame=zmq_socket.recv()
#        frame = open('../frame.jpg', 'rb').read()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@app.route('/video_feed')
def video_feed():
    """Video streaming route. Put this in the src attribute of an img tag."""
#    return Response(debug_gen(Camera()),
#                    mimetype='multipart/x-mixed-replace; boundary=frame')
    return Response(gen(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', debug = True, port=20001, threaded=True)
