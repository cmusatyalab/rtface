#! /bin/bash
source /home/${USER}/torch/install/bin/torch-activate
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd $DIR/..
python -m rtface.recognizer.server 2>&1 | tee openface-server.log
