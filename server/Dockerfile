FROM bamos/openface
MAINTAINER Junjue Wang <junjuew@cs.cmu.edu>

RUN apt-get update && apt-get install -y \
    gcc \
    python-dev \
    default-jre \
    python-pip \
    pssh \
    python-psutil \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ARG gabriel_version=3f0e49ecc7fc7eb3615b2d453cb8fccbca674972
RUN cd /root && \
    wget --output-document=gabriel.zip https://github.com/cmusatyalab/gabriel/archive/${gabriel_version}.zip && \
    unzip gabriel.zip && \
    mv gabriel-${gabriel_version} gabriel && \
    pip2 install -r ~/gabriel/server/requirements.txt && \
    rm gabriel.zip
ENV GABRIELPATH /root/gabriel

ADD . /root/rtface
RUN pip2 install -r /root/rtface/server/requirements.txt && \

ADD . /root/openface
RUN python -m pip install --upgrade --force pip
RUN cd ~/openface && \
    ./models/get-models.sh && \
    pip2 install -r requirements.txt && \
    python2 setup.py install && \
    pip2 install --user --ignore-installed -r demos/web/requirements.txt && \
    pip2 install -r training/requirements.txt

EXPOSE 8000 9000
CMD /bin/bash -l -c '/root/openface/demos/web/start-servers.sh'
