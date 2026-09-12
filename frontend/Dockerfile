# syntax=docker/dockerfile:1

# --- build stage ---
FROM node:22-alpine AS build
WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# VITE_API_BASE_URL queda "horneado" en el bundle estático en build-time
# (Vite lo resuelve vía import.meta.env, no en runtime). Debe ser una URL
# que el NAVEGADOR del cliente pueda resolver -no un hostname interno de
# docker compose-, p.ej. la IP/hostname del homelab o el tailnet.
ARG VITE_API_BASE_URL=http://localhost:10000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# --- runtime stage ---
FROM nginx:1.27-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
