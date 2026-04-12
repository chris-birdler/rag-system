# Build Stage
FROM node:18-alpine AS build
WORKDIR /app
ARG REACT_APP_API_URL=/api
ENV REACT_APP_API_URL=$REACT_APP_API_URL
# Disable CRA's inline webpack runtime so our strict CSP
# (script-src 'self') doesn't block the bootstrap script.
ENV INLINE_RUNTIME_CHUNK=false
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

# Production Stage
FROM nginx:alpine
COPY --from=build /app/build /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
