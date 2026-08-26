FROM 163.50.34.38:5002/system/node:trixie-slim
# FROM 163.50.34.38:5001/system/node:18.19.1-buster-slim

# Create app directory
WORKDIR /usr/src/app

# Copy app into container
COPY dist/ ./dist/

# Copy serve module into container
COPY vendor/node_modules/ ./node_modules/

EXPOSE 5173

CMD ["node", "node_modules/serve/build/main.js", "-s", "dist", "-l", "tcp://0.0.0.0:5173"]