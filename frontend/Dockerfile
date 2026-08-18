# Multi-stage production Dockerfile for the React frontend.
#
# Stage 1 (builder): installs dependencies and builds the Vite bundle.
# Stage 2 (runtime): nginx serving the static files from dist/.

# ---------- Stage 1: builder ----------
FROM node:20-alpine AS builder

WORKDIR /app

# Copy manifests first for layer caching (npm ci is reproducible).
COPY package.json package-lock.json ./
RUN npm ci

# Copy the rest of the source and build the production bundle.
COPY . .
RUN npm run build

# ---------- Stage 2: runtime ----------
FROM nginx:alpine AS runtime

# Custom nginx config (SPA fallback, gzip, caching).
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy the built static assets into the nginx web root.
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

# Health check against the served index (busybox wget ships with nginx:alpine).
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/ > /dev/null 2>&1 || exit 1

CMD ["nginx", "-g", "daemon off;"]
