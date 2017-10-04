# Overview
RTFace is a framework that selectively blurs a person's face based on his identity in real-time to protect user's privacy.
It leverages object tracking to achieve real-time while running face detection using [dlib](http://dlib.net), and face recognition using [OpenFace](https://cmusatyalab.github.io/openface).

# Server Setup
## Use RTFace container
docker pull jamesjue/rtface

## Installation by Hand

### Install Dependencies

You can use Dockerfile as a reference.

You'll need to install following dependencies by hand as specified by its project:

* [OpenFace](https://cmusatyalab.github.io/openface/setup)
* [Gabriel](https://github.com/cmusatyalab/gabriel)

In addition, install other dependencies as follows
```
sudo apt-get install redis-server && pip install -r server/requirements.txt
```

# Client
You need a computer with a **camera** to run the client.

#Installation
## Dependency
* OpenCV (>=2.4)
* pyQt4

```
sudo apt-get install libopencv-dev python-opencv python-qt4
```
## rtface-client
```
wget https://github.com/junjuew/RTFace-pyclient/archive/v0.1.zip
unzip v0.1.zip
```
# Run
1. modify following fields in config.py to point to correct RTFace server
  * GABRIEL_IP: RTFace Server IP
  * VIDEO_STREAM_PORT: 9098 unless you change the port when running RTFace server
  * RESULT_RECEIVING_PORT: 9101 unless you change the port when running RTFace server
2.
```
cd RTFace-pyclient-0.1
./ui.py
```
3. Please follow the [video](https://youtu.be/gQa8oScFS94) to use the interface.
4. Tips for training a person's face
  * 30 seconds of training is good enough
  * please ask the user to turn the face slightly to the right, left, up, and down to capture different angles.
  * RTface uses a frontal face detector, a profile face (a face that has completed turned 90 degree to the left/right) won't
  have too much luck to be detected.



# What's in this repository?
+ [start_demo](https://github.com/cmusatyalab/openface/tree/master/batch-represent): Privacy Mediator Demo Server.
+ [util](https://github.com/cmusatyalab/openface/tree/master/util): Utility scripts.


# Use start_demo.sh

## Environment Variables
   * GABRIELPATH: Path to Gabriel
   * TORCHPATH: if specified, ${TORCHPATH}/bin/activate will be source to activate torch

## Ports
   * 10001: Trainer face recognition websocket server
   * 10002: Trainer Web Server
   * 10003: Policy API Server
   * 10004: Broadcast Web Server
