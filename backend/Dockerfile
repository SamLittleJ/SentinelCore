# The API, its migrations and its command line in one image: the migration
# Job runs the same code the API serves. Base images are pinned by digest.

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1 AS build
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

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
ARG REVISION=unknown
LABEL org.opencontainers.image.title="sentinelcore-backend" \
      org.opencontainers.image.source="https://github.com/SamLittleJ/SentinelCore" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"
RUN useradd --uid 10001 --no-create-home --shell /usr/sbin/nologin sentinelcore
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
