FROM node:22-bookworm-slim
WORKDIR /app
COPY package.json package-lock.json ./
COPY chat-app-example/package.json ./chat-app-example/package.json
RUN npm ci
COPY chat-app-example ./chat-app-example
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start", "--workspace", "@online-consult/chat-app-example"]
