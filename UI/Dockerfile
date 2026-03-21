FROM node:20-slim

WORKDIR /app

# Copy package files and install dependencies
COPY package.json package-lock.json ./
RUN npm ci

# Copy source code
COPY tsconfig.json tsconfig.ui.json vite.config.ts index.html ./
COPY src/ src/

# Expose ports: 3001 = Express API, 5173 = Vite dev server
EXPOSE 3001 5173
