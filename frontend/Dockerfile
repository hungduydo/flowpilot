FROM node:20-alpine

WORKDIR /app

# Install dependencies
COPY package.json package-lock.json* ./
RUN npm install || echo "No package.json yet, skipping install"

# Copy source
COPY . .

EXPOSE 3000

# Dev mode with hot reload
CMD ["npm", "run", "dev"]
