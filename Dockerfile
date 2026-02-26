FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y tzdata xvfb \
    && ln -snf /usr/share/zoneinfo/America/Sao_Paulo /etc/localtime \
    && echo "America/Sao_Paulo" > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps

COPY . .

CMD ["xvfb-run", "-a", "python", "scheduler.py"]
