#!/bin/bash

set -e -u

function die { echo $1; exit 42; }

WEBSOCKET_PORT=9001
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

case $# in
  0) ;;
  1) HTTP_PORT=$1
     ;;
  2) WEBSOCKET_PORT=$2
     ;;
  *) die "Usage: $0 <HTTP Server Port> <WebSocket Port>"
     ;;
esac

cd $(dirname $0)
trap 'kill $(jobs -p)' EXIT

WEBSOCKET_LOG='/tmp/openface.websocket.log'
printf "WebSocket Server: Logging to '%s'\n\n" $WEBSOCKET_LOG
$DIR/websocket-server.py --port $WEBSOCKET_PORT 2>&1 | tee $WEBSOCKET_LOG &

printf "launching trainer website"
$DIR/deploy.sh &
wait
