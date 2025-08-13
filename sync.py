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

def run_sync():
    log("INICIANDO ciclo de sincronização...")
    
    try:
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
    except Exception as e:
        log(f"ERRO: Falha ao conectar com o PostgreSQL: {e}"); return

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
    
    db_devices_data = {}
    try:
        cur.execute("SELECT ip, name, model, port, username, password, enable, input, device_group FROM devices;")
        for row in cur.fetchall():
            ip = row[0]
            db_devices_data[ip] = (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])
    except Exception as e:
        log(f"ERRO: Falha ao ler dados existentes do banco: {e}"); cur.close(); conn.close(); return

    try:
        nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
        if "https://" in NETBOX_URL:
            session = requests.Session()
            session.verify = False
            nb.http_session = session
        devices_from_netbox = nb.dcim.devices.filter(status='active')
        log(f"Encontrados {len(devices_from_netbox)} dispositivos ativos no NetBox.")
        
        netbox_devices_data = {}
        devices_to_insert = []
        for device in devices_from_netbox:
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            ip_address = device.primary_ip4.address.split('/')[0]
            
            use_enable = device.custom_fields.get('oxidized_use_enable', False)
            enable_value = device.custom_fields.get('enable_password') or 'true' if use_enable else None
            input_method = device.custom_fields.get('oxidized_input')
            device_group = device.role.slug if device.role else 'default'

            # Cria uma tupla com todos os dados do dispositivo para comparação
            current_device_tuple_for_comparison = (
                device.name, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_value, input_method, device_group
            )
            # Cria uma tupla com todos os dados para inserção no banco
            current_device_tuple_for_insert = (
                device.name, ip_address, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_value, input_method, device_group
            )
            
            devices_to_insert.append(current_device_tuple_for_insert)
            netbox_devices_data[ip_address] = current_device_tuple_for_comparison

        if db_devices_data != netbox_devices_data:
            log("Mudança detectada nos dados dos dispositivos. Sincronizando e acionando reload.")
            
            cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
            insert_query = "INSERT INTO devices (name, ip, model, port, username, password, enable, input, device_group) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cur.executemany(insert_query, devices_to_insert)
            conn.commit()
            
            log(f"Sincronização CONCLUÍDA. {len(devices_to_insert)} registros inseridos.")
            trigger_oxidized_reload()
        else:
            log("Nenhuma mudança encontrada. Nenhuma ação necessária.")

    except Exception as e:
        log(f"ERRO CRÍTICO durante a sincronização: {e}")
        traceback.print_exc()
        conn.rollback()
    finally:
        cur.close(); conn.close()

if __name__ == '__main__':
    log(f"Serviço de Sincronização iniciado. O trabalho será executado a cada {SYNC_INTERVAL} minuto(s).")
    run_sync()
    schedule.every(SYNC_INTERVAL).minutes.do(run_sync)
    while True:
        schedule.run_pending()
        time.sleep(1)
