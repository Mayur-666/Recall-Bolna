FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# Live-reload target used by docker-compose.dev.yml; source arrives via `docker compose watch` sync.
FROM node:22-alpine AS dev
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 WATCHPACK_POLLING=true
COPY --from=deps /app/node_modules ./node_modules
COPY . .
EXPOSE 3000
CMD ["npx", "next", "dev", "-H", "0.0.0.0", "-p", "3000"]

FROM node:22-alpine AS build
WORKDIR /app
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# public/ isn't tracked in git (the app has no static files there), so make sure it exists for the copy below.
RUN mkdir -p public && npm run build

FROM node:22-alpine AS run
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
