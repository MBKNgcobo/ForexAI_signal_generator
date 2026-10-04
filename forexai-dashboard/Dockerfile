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

# The official nginx entrypoint envsubsts *.template -> conf.d at
# container START, so the upstream URL resolves at run time, not build
# time.
COPY templates/default.conf.template /etc/nginx/templates/default.conf.template

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]