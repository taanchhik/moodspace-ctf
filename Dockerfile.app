FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ .

RUN mkdir -p /data
CMD python init_db.py && python main.py

EXPOSE 5000
