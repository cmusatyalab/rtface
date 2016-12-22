#! /bin/bash
source /home/faceswap-admin/.bashrc && 
gunicorn --workers 2 --bind unix:/tmp/trainer.sock wsgi:app
