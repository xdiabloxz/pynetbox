import os
import pynetbox
import psycopg2
import time
import schedule
from datetime import datetime
import requests
import traceback

# --- CONFIGURAÇÕES (lidas do ambiente) ---
NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL', 5))
OXIDIZED_URL = os.environ.get('OXIDIZED_URL')
# --- NOVAS VARIÁVEIS PARA AUTENTICAÇÃO NO OXIDIZED ---
OXIDIZED_USER = os.environ.get('OXIDIZED_USER')
OXIDIZED_PASS = os.environ.get('OXIDIZED_PASS')
PYTHONUNBUFFERED = os.environ.get('PYTHONUNBUFFERED', 1)

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} - {message}")

def trigger_oxidized_reload():
    if not OXIDIZED_URL:
        log("AVISO: Variável OXIDIZED_URL não definida. Pulando o acionamento da recarga.")
        return
    
    reload_url = f"{OXIDIZED_URL}/reload"
    try:
        log(f"Acionando a recarga dos nós no Oxidized em {reload_url}...")
        
        # Prepara a autenticação se o usuário e senha foram fornecidos
        auth = None
        if OXIDIZED_USER and OXIDIZED_PASS:
            auth = (OXIDIZED_USER, OXIDIZED_PASS)
            log("Usando autenticação para a API do Oxidized.")
            
        # Faz a requisição, agora com o parâmetro 'auth'
        response = requests.get(reload_url, auth=auth, timeout=10)
        
        if response.status_code == 200:
            log("Sinal de recarga enviado ao Oxidized com sucesso.")
        else:
            log(f"ERRO: O Oxidized respondeu com o status {response.status_code} ao tentar recarregar. Verifique as credenciais.")
    except requests.exceptions.RequestException as e:
        log(f"ERRO: Falha ao conectar com a API do Oxidized: {e}")

# ... (A função run_sync() e o Loop Principal permanecem EXATAMENTE IGUAIS) ...
def run_sync():
    log("INICIANDO ciclo de sincronização...")
    # ...
    # O resto da função é idêntico
    # ...
