# pull official base image
FROM python:3.10-slim

# set work directory
WORKDIR /usr/src/app

# set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# install dependencies
RUN pip install --upgrade pip
COPY app.py requirements.txt.in .
RUN pip install -r requirements.txt.in
RUN pip install gunicorn
COPY estimage ./estimage

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "app:app"]
