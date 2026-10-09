FROM python:3.12-slim
WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/klaaryo_contracts /shared/klaaryo_bus

COPY services/push_data_manager/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN cd /shared/klaaryo_contracts && bash generate.sh && pip install --no-cache-dir --no-deps -e .

COPY services/push_data_manager/ .

EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --no-input && python manage.py runserver 0.0.0.0:8000 --noreload"]
