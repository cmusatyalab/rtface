#! /bin/bash

if [ -z ${GABRIEL_ROOT+x} ]
then
   echo "Gabriel Not Found. Please Specify GABRIEL_ROOT to be Gabriel's root path";
else
   echo "User Specifies Gabriel path to be ${GABRIEL_ROOT}";
fi

echo -e "launching Gabriel at dir ${GABRIEL_ROOT}"
source $GABRIEL_ROOT/env/bin/activate
cd $GABRIEL_ROOT/gabriel/server/bin
gabriel-control &
sleep 5
# specify localhost and port to make sure we are connecting to the correct gabriel control server
gabriel-ucomm -s 127.0.0.1:8021 &
sleep 5
wait
