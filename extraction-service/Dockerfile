FROM python:3.12-slim

WORKDIR /app

# Tesseract is the OCR engine (via pytesseract) for scanned/image PDFs — OCR is
# a Phase-1 MUST-have (see docs/PRD-knowledge-graph-mvp.md), so it ships in the
# base image rather than as an optional add-on.
RUN apt-get update \
    && apt-get install -y --no-install-recommends tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Default: process a PDF mounted at /data and write the graph to /out.
# Override the args in docker-compose or `docker run` to point at another file.
ENTRYPOINT ["python", "-m", "app.main"]
CMD ["/data/the-pragmatic-programmer.pdf"]
