FROM node:22-alpine AS build

WORKDIR /app

COPY binnagent-frontend/package*.json ./
RUN npm ci

COPY binnagent-frontend/ ./
RUN npm run build && npm run build:console

FROM nginx:1.27-alpine

COPY binnagent-frontend/nginx.prod.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/learner
COPY --from=build /app/dist-dev-console /usr/share/nginx/dev-console

EXPOSE 80 5174
