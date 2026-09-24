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

# ─── Stage 2: runtime — nginx serving the build output on :3000 ─────────────
FROM nginx:alpine

# Refresh base OS packages so fixable CVEs published after the base image
# was cut (e.g. libexpat) do not trip Gate 4.
RUN apk upgrade --no-cache

# Replaces the stock default.conf (which listened on :80) — SPA fallback for
# react-router's BrowserRouter lives in nginx.conf next to this file.
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/build /usr/share/nginx/html

# Same port the dev server used, so docker-compose (3000:3000) and the
# Kubernetes manifests (containerPort 3000) keep working unchanged.
EXPOSE 3000
CMD ["nginx", "-g", "daemon off;"]
