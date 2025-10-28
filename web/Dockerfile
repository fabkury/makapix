FROM node:20-alpine

WORKDIR /app

ENV NODE_ENV=development

RUN apk add --no-cache libc6-compat curl

COPY web/package.json web/tsconfig.json web/next.config.mjs web/.eslintrc.cjs web/.prettierrc ./ 
COPY web/src ./src

RUN npm install

EXPOSE 3000

CMD ["npm", "run", "dev"]
