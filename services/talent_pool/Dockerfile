FROM python:3.12-slim
WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/klaaryo_contracts /shared/klaaryo_bus

COPY services/talent_pool/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN cd /shared/klaaryo_contracts && bash generate.sh && pip install --no-cache-dir --no-deps -e .

COPY services/talent_pool/ .

CMD ["sh", "-c", "python manage.py migrate --no-input && python -m talent_pool.main"]
