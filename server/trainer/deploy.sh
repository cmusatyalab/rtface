#! /bin/bash
source /home/faceswap-admin/.bashrc && 
sudo service nginx restart &&
gunicorn --workers 2 --bind unix:/tmp/trainer.sock wsgi:app
