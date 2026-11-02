FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_PATH=/data/incident_history.db

WORKDIR /app
COPY app.py /app/app.py

USER 0:0
EXPOSE 8088

CMD ["python", "-B", "/app/app.py"]
