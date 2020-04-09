FROM bamos/openface
MAINTAINER Satyalab, satya-group@lists.andrew.cmu.edu

RUN apt-get update && apt-get install -y \
    gcc \
    python-dev \
    default-jre \
    python-pip \
    pssh \
    python-psutil 

ARG gabriel_version=3f0e49ecc7fc7eb3615b2d453cb8fccbca674972
RUN cd /root && \
    wget --output-document=gabriel.zip https://github.com/cmusatyalab/gabriel/archive/${gabriel_version}.zip && \
    unzip gabriel.zip && \
    mv gabriel-${gabriel_version} gabriel && \
    pip2 install -r ~/gabriel/server/requirements.txt && \
    rm gabriel.zip

RUN apt-get update && apt-get install -y redis-server

ADD . /root/rtface/
RUN pip2 install -r /root/rtface/requirements.txt
RUN /root/rtface/RTFace/openface-server/models/get-models.sh

RUN apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

ENV TORCHPATH /root/torch/install
ENV GABRIELPATH /root/gabriel

EXPOSE 9098 9111 10001 10002 10003 10004

CMD ["/bin/bash", "-l", "/root/rtface/start_demo.sh"]
