#! /bin/bash

USER=$(whoami)

echo -e "launching Gabriel at dir ${GABRIEL_ROOT}"
source $GABRIEL_ROOT/env/bin/activate
cd $GABRIEL_ROOT/gabriel/server/bin
gabriel-control &
sleep 5
# specify localhost and port to make sure we are connecting to the correct gabriel control server
gabriel-ucomm -s 127.0.0.1:8021 &
sleep 5
wait
