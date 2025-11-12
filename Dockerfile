# ==============================
FROM registry.access.redhat.com/ubi9/python-312 AS appbase
# ==============================

# Branch or tag used to pull python-uwsgi-common.
ARG UWSGI_COMMON_REF=main

USER root
WORKDIR /hauki

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV STATIC_ROOT /srv/static

COPY --chown=default:root requirements.txt .

# nmap-ncat (nc) installed for in-container manual debugging
# we need the Finnish locale built
RUN dnf update -y && dnf install -y \
    postgresql \
    nmap-ncat \
    gettext \
    glibc-locale-source \
    && pip install -U pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && localedef --inputfile=fi_FI --charmap=UTF-8 fi_FI.UTF-8 \
    && mkdir -p /usr/local/lib/uwsgi/plugins \
    && uwsgi --build-plugin https://github.com/City-of-Helsinki/uwsgi-sentry \
    && mv sentry_plugin.so /usr/local/lib/uwsgi/plugins/ \
    && dnf clean all

# Build and copy specific python-uwsgi-common files.
ADD https://github.com/City-of-Helsinki/python-uwsgi-common/archive/${UWSGI_COMMON_REF}.tar.gz /usr/src/
RUN mkdir -p /usr/src/python-uwsgi-common && \
    tar --strip-components=1 -xzf /usr/src/${UWSGI_COMMON_REF}.tar.gz -C /usr/src/python-uwsgi-common && \
    cp /usr/src/python-uwsgi-common/uwsgi-base.ini /hauki/ && \
    uwsgi --build-plugin /usr/src/python-uwsgi-common && \
    rm -rf /usr/src/${UWSGI_COMMON_REF}.tar.gz && \
    rm -rf /usr/src/python-uwsgi-common

# Keep media in its own directory outside home, in case home
# directory forms some sort of attack route
# Usually this would be some sort of volume
# RUN mkdir -p /srv/media && chown hauki:hauki /srv/media

ENTRYPOINT ["deploy/entrypoint.sh"]
EXPOSE 8000/tcp

# ==============================
FROM appbase AS development
# ==============================

COPY --chown=default:root requirements-dev.txt .
RUN pip install --no-cache-dir -r requirements-dev.txt

COPY --chown=default:root . .

USER default

# ==============================
FROM appbase AS production
# ==============================

COPY --chown=default:root . .
RUN SECRET_KEY="only-used-for-collectstatic" python manage.py collectstatic --noinput

USER default
