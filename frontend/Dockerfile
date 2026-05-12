FROM node:20-alpine

WORKDIR /app

RUN apk add --no-cache openssl && mkdir -p /certs && chown -R node:node /certs

COPY package.json package-lock.json* ./

RUN npm install

COPY . .

RUN chown -R node:node /app
USER node

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
