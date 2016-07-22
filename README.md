# Privacy Mediator

---

---

## Overview ##

## Installation Guide ##
+ Install openblas, lapack before install any following dependencies to make the code faster:

          sudo apt-get install libopenblas-dev liblapack-dev          

+ Install numpy, scipy from pip to make sure they are using the correct blas and lapack libaries. Use numpy.show_config() to check openblas are used. See [StackOverflow question](http://stackoverflow.com/questions/21671040/link-atlas-mkl-to-an-installed-numpy/21673585#21673585) and this [blog](http://gromgull.net/blog/2013/07/multithreaded-scipynumpy-with-openblas-on-debian/) for numbers using different blas libraries

          sudo pip install numpy scipy


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

## Licensing ##
Unless otherwise stated, the source code are copyright Carnegie Mellon University and licensed under the Apache 2.0 License.

## Author ##
Junjue Wang: junjuew at cs dot cmu dot edu
