FROM node:22-alpine AS build

ARG NPM_REGISTRY=https://registry.npmjs.org

ENV PNPM_HOME=/pnpm
ENV PATH=$PNPM_HOME:$PATH

WORKDIR /app/frontend

RUN corepack enable

COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN pnpm install --registry "$NPM_REGISTRY" --frozen-lockfile

COPY frontend ./
RUN pnpm build

FROM nginxinc/nginx-unprivileged:1.27-alpine

COPY --from=build /app/frontend/dist /usr/share/nginx/html
COPY docker/frontend.conf /etc/nginx/conf.d/default.conf

USER nginx

EXPOSE 8080
