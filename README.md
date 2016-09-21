# Privacy Mediator

## Overview ##
Privacy Mediator is leverage the emerging cloudlet infrastructure to protect leaks of sensitive information from IoT devices.

## Privacy Mediator Server Setup ##
### Dependency ###

+ Compile and install dlib and opencv from source
  + for dlib

        sudo python setup.py install --yes USE_AVX_INSTRUCTIONS | tee build.log

    A correctly installed dlib should be able to run its object detection example more than 100 fps. See dlib's [blog post] (http://blog.dlib.net/2015/02/dlib-1813-released.html)

  + for opencv

        cmake -D CMAKE_BUILD_TYPE=RELEASE -D CMAKE_INSTALL_PREFIX=/usr/local -D WITH_TBB=ON WITH_EIGEN=ON -D WITH_OPENGL=ON .. 2>&1 | tee configure.log
        make -j$(nproc)
        sudo make install

### Dependency ###
* [dlib (19.0)](https://github.com/davisking/dlib/releases/tag/v19.0)
* opencv (>=2.4)
* [openface](https://github.com/cmusatyalab/openface/releases/tag/0.2.1)
* [gabriel](https://github.com/cmusatyalab/gabriel/releases/tag/mobisys2016submission)

### Usage ###
To start server, run server/start_demo.sh

## Author ##
Junjue Wang: junjuew at cs dot cmu dot edu
