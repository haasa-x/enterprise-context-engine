# Admin Graph Viewer — static single-page app.
# No build step, no npm, no bundler: plain HTML + CSS + vanilla JS served by
# Python's built-in static file server on port 3000.
FROM python:3.12-slim

WORKDIR /app
COPY index.html styles.css app.js README.md ./

EXPOSE 3000

# -d /app pins the served directory regardless of the working directory.
CMD ["python", "-m", "http.server", "3000", "-d", "/app"]
