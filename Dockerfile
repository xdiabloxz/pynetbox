FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY adapter.py .

EXPOSE 5000

# --- MUDANÇA FINAL AQUI ---
# Inicia a aplicação usando o servidor de produção Gunicorn
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:5000", "adapter:app"]
