FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY proto/ ./proto/
COPY src/ ./src/
WORKDIR /app/src
EXPOSE 50051
CMD ["python", "main.py"]
