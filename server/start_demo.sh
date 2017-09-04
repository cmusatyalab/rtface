#! /bin/bash

USER=$(whoami)
echo "sourcing torch: "
echo "/home/${USER}/torch/install/bin/torch-activate"
source /home/${USER}/torch/install/bin/torch-activate

# need to pull models down if they doesn't exist yet
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
echo "Work dir is ${DIR}"

openface_model_dir=$DIR/openface-server/models
dlib_face_model=$openface_model_dir/dlib/shape_predictor_68_face_landmarks.dat
openface_model=$openface_model_dir/openface/nn4.small2.v1.t7
if [ ! -f $dlib_face_model ] || [ ! -f $openface_model ]; then
    echo -e "start downloading models"
    $openface_model_dir/get-models.sh
fi

echo -e "launching Privacy Mediator at dir $DIR"
$DIR/start_gabriel.sh 2>&1 | tee gabriel.log &
sleep 15

    
if pgrep -f "gabriel-ucomm" > /dev/null
then
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


# for trial in $(seq 1 5);
# do
#     if ! pgrep -f "openface_server.lua" > /dev/null;
#     then
# 	echo 'checking openface server status:'
# 	echo $trial
# 	echo 'openface server has not finished starting. wait for another 20 seconds...'
# 	sleep 20
#     else
# 	break
#     fi
# done
