FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip \
    && pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

EXPOSE 8000
EXPOSE 8085

ENV WEB_HOST=0.0.0.0
ENV WEB_PORT=8000
ENV TCP_HOST=0.0.0.0
ENV TCP_PORT=8085
ENV INFRACOUNT_NO_BROWSER=1
ENV DB_DRIVER=sqlite
ENV DB_SQLITE_PATH=/app/data/infrared.db

CMD ["python", "tools/launcher.py"]

