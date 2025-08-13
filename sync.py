import os
import pynetbox
import psycopg2
import time
import schedule
from datetime import datetime
import requests

# --- CONFIGURAÇÕES (lidas do ambiente) ---
NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL', 5))
OXIDIZED_URL = os.environ.get('OXIDIZED_URL')

def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} - {message}")

def trigger_oxidized_reload():
    if not OXIDIZED_URL:
        log("AVISO: Variável OXIDIZED_URL não definida. Pulando o acionamento da recarga.")
        return
    reload_url = f"{OXIDIZED_URL}/reload"
    try:
        log("Sinal de recarga enviado ao Oxidized...")
        response = requests.get(reload_url, timeout=10)
        if response.status_code == 200:
            log("Sinal de recarga processado pelo Oxidized com sucesso.")
        else:
            log(f"ERRO: O Oxidized respondeu com o status {response.status_code} ao tentar recarregar.")
    except requests.exceptions.RequestException as e:
        log(f"ERRO: Falha ao conectar com a API do Oxidized: {e}")

def run_sync():
    log("INICIANDO ciclo de sincronização...")
    
    # ... (Conexão com NetBox é igual) ...
    try:
        nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
        if "https://" in NETBOX_URL:
            session = requests.Session()
            session.verify = False
            nb.http_session = session
        devices_from_netbox = nb.dcim.devices.filter(status='active')
        log(f"Encontrados {len(devices_from_netbox)} dispositivos ativos no NetBox.")
    except Exception as e:
        log(f"ERRO: Falha ao conectar ou buscar dados do NetBox: {e}"); return

    # ... (Conexão com PostgreSQL é igual) ...
    try:
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
    except Exception as e:
        log(f"ERRO: Falha ao conectar com o PostgreSQL: {e}"); return

    # Garante que a tabela tem a nova coluna 'device_group'
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, port INTEGER NOT NULL, username TEXT NOT NULL,
            password TEXT NOT NULL, enable TEXT, input TEXT, device_group TEXT
        );
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS enable TEXT;
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS input TEXT;
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS device_group TEXT;
    """)
    conn.commit()

    try:
        # Busca a lista de IPs ATUAL no banco de dados
        cur.execute("SELECT ip FROM devices;")
        ips_in_db = {row[0] for row in cur.fetchall()}
        
        # Monta a lista de dispositivos do NetBox
        devices_to_insert = []
        ips_from_netbox = set()
        for device in devices_from_netbox:
            if not all([...]): continue # Mesma verificação de antes

            ip_address = device.primary_ip4.address.split('/')[0]
            ips_from_netbox.add(ip_address)
            
            use_enable = device.custom_fields.get('oxidized_use_enable', False)
            enable_value = device.custom_fields.get('enable_password') or 'true' if use_enable else None
            input_method = device.custom_fields.get('oxidized_input')
            # Busca a função (role) do dispositivo e usa o 'slug' (nome amigável)
            device_group = device.role.slug if device.role else 'default'

            devices_to_insert.append((
                device.name, ip_address, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_value, input_method, device_group
            ))

        # Compara as listas de IPs para ver se houve mudança
        if ips_in_db != ips_from_netbox:
            log("Mudança detectada na lista de dispositivos. Atualizando o banco de dados e acionando o reload.")
            
            cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
            insert_query = "INSERT INTO devices (name, ip, model, port, username, password, enable, input, device_group) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cur.executemany(insert_query, devices_to_insert)
            conn.commit()
            
            log(f"Sincronização CONCLUÍDA. {len(devices_to_insert)} registros inseridos.")
            trigger_oxidized_reload() # Aciona o reload apenas se houve mudança
        else:
            log("Nenhuma mudança encontrada na lista de dispositivos. Nenhuma ação necessária.")

    except Exception as e:
        log(f"ERRO: Falha durante a sincronização: {e}"); conn.rollback()
    finally:
        cur.close(); conn.close()

# ... (Loop Principal é igual) ...
