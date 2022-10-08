ARG APP_IMAGE=python:3.9-alpine

FROM $APP_IMAGE AS base
FROM base as builder

RUN mkdir /install
WORKDIR /install

COPY requirements.txt /requirements.txt

RUN pip install --prefix=/install -r /requirements.txt

FROM base
WORKDIR /project
COPY --from=builder /install /usr/local
ADD . /project

RUN apk add --no-cache curl

ENTRYPOINT python app.py
