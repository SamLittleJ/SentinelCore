# The API, its migrations and its command line in one image: the migration
# Job runs the same code the API serves. Base images are pinned by digest.

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b AS build
# Every dependency is pinned with its hashes (requirements.lock, generated
# with `uv pip compile --generate-hashes`): a changed package is refused.
COPY requirements.lock /tmp/requirements.lock
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --require-hashes -r /tmp/requirements.lock
COPY alembic.ini /srv/sentinelcore/
COPY app /srv/sentinelcore/app
COPY migrations /srv/sentinelcore/migrations
# Compiled now, since the running container cannot write.
RUN /opt/venv/bin/python -m compileall -q /srv/sentinelcore /opt/venv

FROM python:3.12-slim@sha256:5e2bdb1b0d542d5039cffb8181c65930093949194a65c365dfb1b0fe13a4fa5b
ARG REVISION=unknown
LABEL org.opencontainers.image.title="sentinelcore-backend" \
      org.opencontainers.image.source="https://github.com/SamLittleJ/SentinelCore" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"
# zlib1g deb13u1 fixes CVE-2026-85091, and libc6 and libc-bin deb13u5 fix
# CVE-2026-19499 and CVE-2026-5435, which the base image does not have yet
# (`make scan-images`). Remove each once the base image's digest includes it.
RUN apt-get update \
    && apt-get install -y --no-install-recommends zlib1g=1:1.3.dfsg+really1.3.1-1+deb13u1 \
       libc6=2.41-12+deb13u5 libc-bin=2.41-12+deb13u5 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sentinelcore
COPY --from=build /opt/venv /opt/venv
COPY --from=build /srv/sentinelcore /srv/sentinelcore
WORKDIR /srv/sentinelcore
# FORWARDED_ALLOW_IPS: the proxies whose X-Forwarded-For uvicorn believes;
# none but this container until the deployment names nginx's addresses.
ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FORWARDED_ALLOW_IPS=127.0.0.1
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--no-server-header"]
