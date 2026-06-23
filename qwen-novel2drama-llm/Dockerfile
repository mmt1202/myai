FROM python:3.11-slim

WORKDIR /app
COPY requirements-api.txt ./requirements-api.txt
RUN pip install --no-cache-dir -r requirements-api.txt
COPY inference ./inference
COPY prompts ./prompts
EXPOSE 8000
CMD ["python", "inference/api_server.py", "--help"]
