FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for OpenCV, PaddleOCR, and Tesseract
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ app/

# Pre-download EasyOCR English model at build time so startup is instant
RUN python3 -c "import easyocr; easyocr.Reader(['en'], gpu=False)" || true

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
