# Overview
RTFace is a framework that selectively blurs a person's face based on his identity in real-time to protect user's privacy.
It leverages object tracking to achieve real-time while running face detection using [dlib](http://dlib.net), and face recognition using [OpenFace](https://cmusatyalab.github.io/openface).

# What's in this repository?
+ [RTFace](https://github.com/junjuew/rtface/tree/master/RTFace): RTFace module for doing real-time face denaturing.
+ [trainer](https://github.com/junjuew/rtface/tree/master/trainer): Trainer web server for registering faces.
+ [policy](https://github.com/junjuew/rtface/tree/master/policy): Policy API server for specifying user's denaturing policy.
+ [broadcast](https://github.com/junjuew/rtface/tree/master/broadcast): Broadcast server for viewing denatured video streams.
+ [camera-source](https://github.com/junjuew/rtface/tree/master/camera-source): Video streaming from a webcamera
+ [start_demo.sh](https://github.com/junjuew/rtface/tree/master/start_demo.sh): script to start the demo.
+ [kill_demo.sh](https://github.com/junjuew/rtface/tree/master/kill_demo.sh): script to kill the demo.
+ [Dockerfile](https://github.com/junjuew/rtface/tree/master/Dockerfile):
  Dockerfile for building server container image
+ [Dockerfile-client](dockerfile-client): Dockerfile for building client
  container image

# Server Setup
## Installation
### Option 1. Download pre-build RTFace container image.

```
docker pull jamesjue/rtface
```

### Option 2. Clone this repo and build the image yourself.

```
docker build -t <image-name> .
```

### Option 3. Installation by Hand

#### Install Dependencies

You should use Dockerfile as a reference.

You'll need to install following dependencies by hand as specified by its project:

* [OpenFace](https://cmusatyalab.github.io/openface/setup)
* [Gabriel](https://github.com/cmusatyalab/gabriel)

In addition, install other dependencies as follows
```
sudo apt-get install redis-server && pip install -r server/requirements.txt
```

## Run Server

If you're using docker image, use

```
docker run -it --rm --name <container-name> \
-p 0.0.0.0:9098:9098 -p 0.0.0.0:9111:9111 -p 0.0.0.0:10001-10004:10001-10004 \
jamesjue/rtface
```

If you installed everything by hand, use
```
./start_demo.sh
```

For start_demo.sh, you need to set following environment variables:

   * GABRIELPATH: Path to Gabriel
   * TORCHPATH: if specified, ${TORCHPATH}/bin/activate is sourced to activate torch

Here are ports the server opens:

   * 10002: Trainer Web Server: Used to collect training images
   * 10003: Policy API Server ("showFace" or "blurFace"): Used to convey user's privacy policy
   * 10004: Broadcast Web Server: for viewing privacy-aware video stream

# Client

## Setup
To set up video streaming source
([camera-source](https://github.com/junjuew/rtface/tree/master/camera-source)):

### Option 1: Container

```
docker run --privileged --rm -it --net host \
--volume=/home/junjuew/.Xauthority:/root/.Xauthority:rw \
--env DISPLAY=:0 --env QT_X11_NO_MITSHM=1 \
--env SERVER_IP=<your server ip> \
jamesjue/rtface-client
```

### Option 2: Manual Installation

   * Install dependency:
   ```
   sudo apt-get install libopencv-dev python-opencv python-qt4
   ```
   * set environment variable SERVER_IP to be the IP address of the rtface server
   * Run
   ```
   cd camera-source
   ./ui.py
   ```

## How to use
The client includes a training webpage to add/delete new users,
a desktop GUI as the video source stream,
and a broadcast
webpage showing the denatured video stream.

   * To train a face to be recognized, go to **https://hostname:10002**. You'll need to accept self-signed certificate.
   * To change a user's policy, send HTTP post form data in the following format to **http://hostname:10002**
   ```
   http --form POST <hostname>:10003/policy uid=<email-id> policy=<"showFace" or "blurFace">
   ```
   * To view video streams after privacy preservation, go to **https://hostname:10004**

## NOTE:

   1. Don't use camera-source's UI to add user, control user's policy, nor delete uesr.
   2. Instead, to add user, you should use trainer web server.
   3. To control user's policy, use policy web server.
   4. To delete a user, log in trainer web user and click "Clear". A user is no longer registered with the system when there are no his/her training images.
   5. For the trainer web page, if you're running the server inside a container, Google Auth doesn't work due to domain name requirement. Just use email to log in.

# FAQ
## Tips for training a person's face
  * 30 seconds of training is good enough
  * please ask the user to turn the face slightly to the right, left, up, and down to capture different angles.
  * RTface uses a frontal face detector, a profile face (a face that has completed turned 90 degree to the left/right) won't
  have too much luck to be detected.
