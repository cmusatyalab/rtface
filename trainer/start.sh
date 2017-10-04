#!/bin/bash

set -e -u

FACE_RECOGNITION_WEBSOCKET_PORT=10001
TRAINER_WEB_PORT=10002
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo $DIR

cd $DIR
WEBSOCKET_LOG='/tmp/trainer.websocket.log'
echo "Face Recognition WebSocket Server: Logging to $WEBSOCKET_LOG"
python2 $DIR/face-recognition-websocket-server.py --port $FACE_RECOGNITION_WEBSOCKET_PORT 2>&1 | tee $WEBSOCKET_LOG &

echo "launching trainer website"
# gunicorn --workers 2 --bind 0.0.0.0:$TRAINER_WEB_PORT wsgi:app
# use flask debug server for now
python2 $DIR/trainer.py
wait
