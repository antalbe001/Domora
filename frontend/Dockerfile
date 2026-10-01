# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app

# The node images ship npm 10.9.x, which crashes resolving this dependency
# tree (a bug in its peer resolver), so pin a newer npm explicitly.
RUN npm install -g npm@12

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s \
    CMD wget -qO- http://localhost/ >/dev/null || exit 1
