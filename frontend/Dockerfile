# ─── Stage 1: build the static site ─────────────────────────────────────────
# The old image shipped node:14 (EOL) plus the whole CRA dev server and
# node_modules into production: 230 High/Critical CVEs, almost all from the
# react-scripts@4 toolchain — Gate 4 (Grype) can never pass that. A static
# build has no node_modules at runtime at all.
FROM node:20-alpine AS build
WORKDIR /app

# react-scripts 4 pins webpack 4, whose md4 hashing was removed from
# OpenSSL 3 (Node 17+). Without this flag the build dies with
# "error:0308010C:digital envelope routines::unsupported".
ENV NODE_OPTIONS=--openssl-legacy-provider

# copy the lock file too, so the install is reproducible
COPY package.json package-lock.json ./

# install exact versions from package-lock.json
RUN npm ci

# copy rest files
COPY . .

# production build -> /app/build
RUN npm run build

# ─── Stage 2: runtime — nginx serving the build output on :8080 ─────────────
FROM nginx:alpine

# Refresh base OS packages so fixable CVEs published after the base image
# was cut (e.g. libexpat) do not trip Gate 4.
RUN apk upgrade --no-cache

# Replaces the stock default.conf (which listened on :80) — SPA fallback for
# react-router's BrowserRouter lives in nginx.conf next to this file.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

# ── OpenShift (arbitrary UID) compatibility ────────────────────────────────
# OpenShift never runs this image as root: the SCC assigns an arbitrary UID
# which is always a member of group 0 (root). Three things follow, and all
# three are handled here:
#
#   1. The stock `user nginx;` directive is dropped. nginx can only switch
#      the worker's UID when the master starts as root; as a non-root master
#      it just logs "the user directive makes sense only if the master
#      process runs with super-user privileges" and keeps the master's UID.
#   2. Everything nginx writes at runtime must be group-0 writable
#      (chmod g=u), not just group-writable. OpenShift guarantees the
#      container UID is in group 0, but nothing guarantees it is UID 0.
#      Without this the master dies at startup with
#      `mkdir() "/var/cache/nginx/client_temp" failed (13: Permission denied)`
#      and the pod CrashLoopBackOffs.
#   3. The temp dirs are pre-created at build time so a read-only or
#      non-creatable /var/cache/nginx cannot fail the start.
#
# /run (aka /var/run) holds nginx.pid and needs the same treatment, otherwise
# the start fails one step later. /usr/share/nginx/html is left as-is: the
# build output is world-readable (0644/0755), so the arbitrary UID can serve
# it without any ownership change.
RUN sed -i '/^user /d' /etc/nginx/nginx.conf \
 && mkdir -p /var/cache/nginx/client_temp \
              /var/cache/nginx/proxy_temp \
              /var/cache/nginx/fastcgi_temp \
              /var/cache/nginx/uwsgi_temp \
              /var/cache/nginx/scgi_temp \
 && chgrp -R 0 /var/cache/nginx /run \
 && chmod -R g=u /var/cache/nginx /run

# Unprivileged port, so the Service on :3000 and docker-compose both keep
# working unchanged while the container itself stays SCC-compliant.
EXPOSE 8080
CMD ["nginx", "-g", "daemon off;"]
