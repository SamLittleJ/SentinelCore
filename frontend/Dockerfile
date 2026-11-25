# The console: the production build, served by nginx as a non-root user.
# Base images are pinned by digest, so a rebuild uses the same bytes.

FROM node:22-alpine@sha256:1314fb30ec37592d5845e5a160d522c0e680972aa534549940b8d73bde88481a AS build
WORKDIR /console
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build \
    && node scripts/nginx-headers.ts > console-headers.conf

FROM nginxinc/nginx-unprivileged:stable-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03
ARG REVISION=unknown
LABEL org.opencontainers.image.title="sentinelcore-console" \
      org.opencontainers.image.source="https://github.com/SamLittleJ/SentinelCore" \
      org.opencontainers.image.revision="${REVISION}" \
      org.opencontainers.image.licenses="MIT"
# Fixed packages the base image does not have yet (`make scan-images`):
# zlib 1.4-r0 (1.3.2-r1 fixed CVE-2026-85091; Alpine has since dropped it),
# brotli-libs 1.2.1-r0 fixes CVE-2026-111497, curl and libcurl 8.23.0-r0 fix
# CVE-2026-92392, libexpat 2.10.0-r0 fixes CVE-2026-113351, -115506, -117610
# and -118370, musl and musl-utils 1.2.6-r3 fix CVE-2026-107891, libxslt
# 1.1.43-r4 fixes CVE-2026-9947, -87636 and -125350, libcrypto3 and libssl3
# 3.5.9-r1 fix CVE-2026-88823, -95691, -95692 and -107496, libxml2 2.13.9-r3
# fixes CVE-2026-86144. nginx 1.30.7-r1 fixes CVE-2026-113425, -118899,
# -121810, -123007, -123633 and -123634; it comes from nginx.org, like the
# base image's own nginx (signed with the nginx_signing key the image already
# trusts), and its modules are pinned to the exact nginx version, so they move
# with it. Remove each once the base image's digest includes it.
USER root
RUN apk add --no-cache zlib=1.4-r0 brotli-libs=1.2.1-r0 \
        curl=8.23.0-r0 libcurl=8.23.0-r0 libexpat=2.10.0-r0 \
        musl=1.2.6-r3 musl-utils=1.2.6-r3 libxslt=1.1.43-r4 \
        libcrypto3=3.5.9-r1 libssl3=3.5.9-r1 libxml2=2.13.9-r3 \
    && apk add --no-cache \
        --repository https://nginx.org/packages/alpine/v3.24/main \
        nginx=1.30.7-r1 nginx-module-geoip=1.30.7-r1 \
        nginx-module-image-filter=1.30.7-r1 nginx-module-xslt=1.30.7-r1 \
        nginx-module-njs=1.30.7.1.0.2-r1
# The image's own default site is replaced, not added to.
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/proxy.conf /etc/nginx/snippets/proxy.conf
COPY --from=build /console/console-headers.conf /etc/nginx/snippets/console-headers.conf
COPY --from=build /console/dist /usr/share/nginx/html
# nginx (101), the image's unprivileged user; it writes only to /tmp.
USER 101
EXPOSE 8080
