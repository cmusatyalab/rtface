#! /bin/bash

set -e

function die { echo $1; exit 42; }

# Dependency checks
# source torch if user indicates it's not activated by default
if [[ ! -z ${TORCHPATH+x} ]]; then
    torch_activate_path="${TORCHPATH}/bin/torch-activate"
    echo "Activate torch at ${torch_activate_path}"
    source ${torch_activate_path}
fi

if [ -z ${GABRIELPATH+x} ]
then
   die "Gabriel Not Found. Please specify environment variable GABRIELPATH to be Gabriel's root directory";
else
   echo "User specified Gabriel at ${GABRIELPATH}";
fi

# download face detector and recognition models
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
openface_model_dir=$DIR/RTFace/openface-server/models
dlib_face_model=$openface_model_dir/dlib/shape_predictor_68_face_landmarks.dat
openface_model=$openface_model_dir/openface/nn4.small2.v1.t7
if [ ! -f $dlib_face_model ] || [ ! -f $openface_model ]; then
    echo "No models found. Start downloading dlib and openface models"
    $openface_model_dir/get-models.sh
fi

echo "launching Gabriel at ${GABRIELPATH}"
cd $GABRIELPATH/server/bin
./gabriel-control &> /tmp/gabriel-control.log &
sleep 5
./gabriel-ucomm -s 127.0.0.1:8021 -n eth0 &> /tmp/gabriel-ucomm.log &
sleep 5

if pgrep -f "gabriel-ucomm" > /dev/null
then
    if [[ $(redis-cli ping) != 'PONG' ]]; then
        echo 'starting redis...'
        redis-server &
    fi
    echo 'starting trainer...'
    $DIR/trainer/start.sh 2>&1 | tee trainer.log &
    echo 'starting policy server ...'
    $DIR/policy/start.sh 2>&1 | tee policy.log &
    echo 'starting broadcast server ...'
    $DIR/broadcast/start.sh 2>&1 | tee broadcast.log &
    echo 'starting mediator...'
    $DIR/proxy.py -s 127.0.0.1:8021 2>&1
else
    $DIR/kill_demo.sh
    echo "launch failed"
fi

wait
