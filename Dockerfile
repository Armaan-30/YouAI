FROM python:3.12-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends tesseract-ocr tesseract-ocr-hin tesseract-ocr-spa tesseract-ocr-fra tesseract-ocr-deu && rm -rf /var/lib/apt/lists/*
COPY requirements-cloud.txt .
RUN pip install --no-cache-dir -r requirements-cloud.txt
COPY app ./app
COPY web ./web
ENV YOUAI_MODE=cloud YOUAI_DATA_DIR=/var/data/youai YOUAI_TESSDATA=/usr/share/tesseract-ocr/5/tessdata
CMD ["sh", "-c", "exec uvicorn app.cloudapp:app --host 0.0.0.0 --port ${PORT:-10000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
