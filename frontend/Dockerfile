# Stage 1: build the static files.
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: serve them. This image runs nginx as a non-root user, on port 8080.
FROM nginxinc/nginx-unprivileged:stable-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
