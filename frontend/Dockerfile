# React frontend: build with Node, serve the static files with nginx.
# Build:  docker build -t sgw-frontend .
# Run:    docker run -p 5173:80 -e BACKEND_URL=http://backend:8000 sgw-frontend
# nginx forwards /api/* to BACKEND_URL (like the Vite dev proxy), so the browser never needs CORS.

FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
# the nginx image fills ${BACKEND_URL} into templates/*.template at startup
ENV BACKEND_URL=http://backend:8000
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
