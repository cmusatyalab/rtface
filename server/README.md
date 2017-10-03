#Overview
RTFace is a framework that selectively blurs a person's face based on his identity in real-time to protect user's privacy.
It leverages object tracking to achieve real-time while running face detection using [dlib](http://dlib.net), and face recognition using [OpenFace](https://cmusatyalab.github.io/openface).

#Server
## Run
1. Modify "abspath to rtface-server.qcow2" in the domain file rtface-server.xml to be the absolute path of rtface-server.qcow2 vm image
2. boot up the virtual machine
3. ssh (port 40022 defined in rtface-server.xml) into the virtual machine using privacy:mediator(username:password)
4. launch Gabriel communication framework. Notice: Gabriel binds to eth0 interface by default.
If your network interface is not named 'eth0', please modify the 'eth0' in '"def get_ip(iface = 'eth0')" in
/home/privacy/dependency/gabriel/server/gabriel/common/network/util.py to match your interface name
```
cd $gabriel_bin
./gabriel-control
```
```
cd $gabriel_bin
./gabriel-ucomm
```

5. launch openface for face recognition:
```
cd $rtface_bin
./openface-server/cloudlet-demo-openface-server.py 2>&1
```
6. launch rtface:
```
cd $rtface_bin
./proxy.py -s 127.0.0.1:8021 2>&1
```

#Client
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


# Use start_demo.sh

## Environment Variables
   * GABRIELPATH: Path to Gabriel
   * TORCHPATH: if specified, ${TORCHPATH}/bin/activate will be source to activate torch
   
