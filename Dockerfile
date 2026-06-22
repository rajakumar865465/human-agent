FROM python:3.11-slim

WORKDIR /app

COPY requirements-mvp.txt .
RUN pip install --no-cache-dir -r requirements-mvp.txt
RUN python -m playwright install --with-deps chromium

COPY . .

CMD ["python", "main.py"]
