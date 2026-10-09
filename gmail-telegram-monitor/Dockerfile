FROM python:3.12-slim
WORKDIR /app
COPY gmail-telegram-monitor/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY gmail-telegram-monitor/ ./
ENV PYTHONDONTWRITEBYTECODE=1
CMD ["sh", "-c", "uvicorn app:app --host 0.0.0.0 --port ${PORT:-10000}"]
