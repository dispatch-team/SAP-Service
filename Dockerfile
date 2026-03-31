FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY eap-core/eap/ eap-core/eap/
COPY eap-core/data/ eap-core/data/
COPY api/ api/

ENV DATA_DIR=/app/eap-core

EXPOSE 8085

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8085"]
