FROM python:3.12-slim
WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/klaaryo_contracts /shared/klaaryo_bus

COPY services/event_logger/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY services/event_logger/ .

ENV PYTHONUNBUFFERED=1
CMD ["sh", "-c", "python manage.py migrate --no-input && python -m event_logger.main"]
