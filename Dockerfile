ARG PYTHON_VERSION=3.11.9
FROM python:${PYTHON_VERSION}-slim



LABEL authors="Maximilian Meil"

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /usr/src/app

RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

#RUN --mount=type=bind,source=requirements.txt,target=requirements.txt \
#    python -m pip install --no-cache-dir -r requirements.txt



COPY . .

