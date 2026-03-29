FROM python:3.11-slim

WORKDIR /app

# Copiar código
COPY . /app

# Dependencias
RUN apt-get update && apt-get install -y --no-install-recommends docker-cli docker.io \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir flask requests

# Puerto que expone la app de la plataforma
EXPOSE 3000

# Ejecutar servidor Flask
CMD ["python", "main.py"]
