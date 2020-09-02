ARG BASE_IMAGE=helsinki/hauki:latest

FROM $BASE_IMAGE

# Change back to root for installing stuff
USER root

RUN pip install --no-cache-dir elastic-apm

# Change back to user
USER hauki

COPY local_settings.py .
