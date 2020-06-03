FROM python:3

WORKDIR /usr/src/app

COPY . /usr/src/app

RUN pip install gunicorn && pip install -r requirements.txt


RUN ls /usr/src/app

ENTRYPOINT ["/usr/src/app/run.sh"]
