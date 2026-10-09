FROM python:3.12-slim
WORKDIR /app

COPY shared/ /shared/
RUN pip install --no-cache-dir /shared/klaaryo_contracts /shared/klaaryo_bus

COPY tests/e2e/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN cd /shared/klaaryo_contracts && bash generate.sh && pip install --no-cache-dir --no-deps -e .

COPY tests/e2e/ .

CMD ["pytest", "-v", "test_end_to_end.py"]
