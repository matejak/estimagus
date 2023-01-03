# pull official base image
FROM python:3.10-slim

WORKDIR /usr/src/app

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

COPY app.py requirements.txt.in .
RUN true \
	&& pip install --upgrade pip \
	&& pip install -r requirements.txt.in \
	&& pip install gunicorn \
	&& true
COPY estimage ./estimage

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
