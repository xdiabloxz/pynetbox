# Usa uma imagem base leve do Python
FROM python:3.10-slim

# Define o diretório de trabalho dentro do contêiner
WORKDIR /app

# Copia o arquivo de dependências
COPY requirements.txt .

# Instala as dependências
RUN pip install --no-cache-dir -r requirements.txt

# Copia o script da nossa aplicação
COPY adapter.py .

# Expõe a porta que o Flask vai usar
EXPOSE 5000

# Comando para iniciar a aplicação
CMD ["python", "adapter.py"]
