# ==============================
FROM registry.access.redhat.com/ubi9/python-39 AS appbase
# ==============================

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
    && pip install --no-cache-dir uwsgi \
    && pip install --no-cache-dir -r requirements.txt \
    && localedef --inputfile=fi_FI --charmap=UTF-8 fi_FI.UTF-8 \
    && dnf clean all

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
