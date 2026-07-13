FROM node:22-bookworm-slim

WORKDIR /app

COPY code-verifier/package.json code-verifier/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts

COPY code-verifier/ ./

USER node

EXPOSE 8090

CMD ["node", "server.mjs"]
