FROM node:22-bookworm-slim

ARG NPM_REGISTRY=https://registry.npmjs.org

WORKDIR /app

COPY code-verifier/package.json code-verifier/package-lock.json ./
RUN npm ci --registry "$NPM_REGISTRY" --omit=dev --ignore-scripts

COPY code-verifier/ ./

USER node

EXPOSE 8090

CMD ["node", "server.mjs"]
