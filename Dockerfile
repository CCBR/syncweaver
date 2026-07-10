FROM python:3.14-slim

ARG SYNCWEAVER_VERSION=main

RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir "git+https://github.com/CCBR/syncweaver@${SYNCWEAVER_VERSION}"
