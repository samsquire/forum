#!/usr/bin/env bash
export WORKER_HOST=app ; sudo -E $(which gunicorn) -w 1 -k gevent  dls:app --bind 0.0.0.0:9005 &
export WORKER_HOST=database ; sudo -E $(which gunicorn) -w 1 -k gevent  dls:app --bind 0.0.0.0:9006 &


