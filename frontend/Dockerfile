FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install

# Copy source
COPY . .

# Environment variables (build-time defaults, overridden by docker-compose)
ENV NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_WS_URL=ws://localhost:8000
ENV NEXT_PUBLIC_N8N_URL=http://localhost:5678

EXPOSE 3000

# Dev mode with hot reload
CMD ["npm", "run", "dev"]
