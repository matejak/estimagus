# pull official base image
FROM python:3.11-slim

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY requirements.txt.in .
RUN true \
	&& pip install --upgrade pip \
	&& pip install -r requirements.txt.in \
	&& pip install gunicorn \
	&& true
COPY app.py app_behind_proxy.py .
COPY estimage ./estimage

CMD ["gunicorn", "--timeout", "600", "--workers", "2", "--max-requests-jitter", "100", "--max-requests", "900", "--bind", "0.0.0.0:5000", "app_behind_proxy:app"]
