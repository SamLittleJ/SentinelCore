# The console: the production build, served by nginx as a non-root user.
# Base images are pinned by digest, so a rebuild uses the same bytes.

FROM node:25-alpine@sha256:bdf2cca6fe3dabd014ea60163eca3f0f7015fbd5c7ee1b0e9ccb4ced6eb02ef4 AS build
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
# The image's own default site is replaced, not added to.
COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/proxy.conf /etc/nginx/snippets/proxy.conf
COPY --from=build /console/console-headers.conf /etc/nginx/snippets/console-headers.conf
COPY --from=build /console/dist /usr/share/nginx/html
# nginx (101), the image's unprivileged user; it writes only to /tmp.
USER 101
EXPOSE 8080
