FROM python:3.12-slim
WORKDIR /app
COPY services/fake_ats_alpha/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY services/fake_ats_alpha/ .
EXPOSE 8001
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
