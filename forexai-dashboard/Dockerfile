FROM node:22-alpine AS build

WORKDIR /app

COPY package*.json ./

RUN npm ci

COPY . .

RUN npm run build


FROM nginx:alpine

# Compose default: keeps local docker-compose behavior unchanged.
# On Render this is overridden with the csharp-api service URL.
ENV CSHARP_API_URL=http://csharp-api:8080

# Fallback for ${PORT} in default.conf.template. Render injects PORT itself
# (10000 on the free tier) and overrides this value at runtime; locally
# nothing injects it, and envsubst would render an empty "listen ;", which
# nginx refuses to load. Pinning it here keeps `docker compose up` working
# with the published 80:80 port mapping.
ENV PORT=80

# The official nginx entrypoint envsubsts *.template -> conf.d at
# container START, so the upstream URL resolves at run time, not build
# time.
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]