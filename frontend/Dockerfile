# syntax=docker/dockerfile:1.6
#
# Multi-stage build:
#   Stage 1 (builder): Node image that runs `npm ci` and `npm run build`
#   Stage 2 (runtime): Caddy image that serves dist/ as static files and
#                      reverse-proxies /api/* to the backend container.
#
# Caddy is chosen over nginx because it handles TLS automatically via Let's Encrypt
# with zero config beyond a domain name — and it's tiny (~50MB image).

# ─── STAGE 1: build static files ─────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy only package files first so npm ci is cached when only source changes
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest and build
COPY . .
RUN npm run build


# ─── STAGE 2: serve via Caddy ────────────────────────────────────
FROM caddy:2-alpine AS runtime

# Built static files go to Caddy's default site root
COPY --from=builder /app/dist /srv

# Caddyfile is copied from the frontend directory at build time.
# It lives in the repo so it's version-controlled alongside the code.
COPY Caddyfile /etc/caddy/Caddyfile

EXPOSE 80 443

# Caddy's default CMD handles TLS, HTTP->HTTPS redirect, graceful reload, etc.