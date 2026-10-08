FROM python:3.11-slim

WORKDIR /app

# Instala dependências
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código da aplicação
COPY . .

# Cria diretório persistente para agendamentos
RUN mkdir -p /data

ENV PORT=8000
ENV HOST=0.0.0.0
ENV DATA_DIR=/data

EXPOSE 8000

CMD ["python", "main.py"]
