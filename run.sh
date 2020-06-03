#!/usr/bin/env bash

$(which gunicorn) -w 4 identikit:app --bind 0.0.0.0:80
