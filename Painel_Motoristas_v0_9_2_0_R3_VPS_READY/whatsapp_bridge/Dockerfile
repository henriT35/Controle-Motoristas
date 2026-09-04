FROM node:24-bookworm-slim
WORKDIR /bridge
COPY package.json /bridge/package.json
RUN npm install --omit=dev --no-audit --no-fund
COPY server.mjs /bridge/server.mjs
COPY healthcheck.mjs /bridge/healthcheck.mjs
CMD ["node", "server.mjs"]
