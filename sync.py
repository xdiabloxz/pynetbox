import os
import pynetbox
import psycopg2
import time
import schedule
from datetime import datetime

# --- CONFIGURAÇÕES (lidas do ambiente) ---
NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')
SYNC_INTERVAL = int(os.environ.get('SYNC_INTERVAL', 5))

# --- Função de Log com Data/Hora ---
def log(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    print(f"{timestamp} - {message}")

def run_sync():
    log("INICIANDO ciclo de sincronização...")
    
    # ... (Conexão com NetBox e DB é igual) ...
    try:
        nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
        if "https://" in NETBOX_URL:
            import requests
            session = requests.Session()
            session.verify = False
            nb.http_session = session
        devices_from_netbox = nb.dcim.devices.filter(status='active')
        log(f"Encontrados {len(devices_from_netbox)} dispositivos ativos no NetBox.")
    except Exception as e:
        log(f"ERRO: Falha ao conectar ou buscar dados do NetBox: {e}")
        return
    try:
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
    except Exception as e:
        log(f"ERRO: Falha ao conectar com o PostgreSQL: {e}")
        return

    # 3. Criar/Ajustar a tabela para incluir a coluna 'enable'
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, port INTEGER NOT NULL, username TEXT NOT NULL,
            password TEXT NOT NULL, enable TEXT
        );
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS enable TEXT;
    """)
    conn.commit()

    # 4. Sincronizar dados
    try:
        device_list_to_insert = []
        for device in devices_from_netbox:
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            ip_address = device.primary_ip4.address.split('/')[0]
            
            # --- Lógica para a senha de 'enable' ---
            enable_value = None # Padrão
            use_enable = device.custom_fields.get('oxidized_use_enable', False)
            if use_enable:
                # Se a caixa estiver marcada, verifica se há uma senha.
                # Se não houver senha, define o valor como 'true'
                enable_value = device.custom_fields.get('enable_password') or 'true'

            device_list_to_insert.append((
                device.name, ip_address, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_value
            ))

        cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
        log(f"Tabela 'devices' limpa. Inserindo {len(device_list_to_insert)} novos registros...")
        
        insert_query = "INSERT INTO devices (name, ip, model, port, username, password, enable) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        cur.executemany(insert_query, device_list_to_insert)

        conn.commit()
        log("Sincronização CONCLUÍDA com sucesso!")
    except Exception as e:
        log(f"ERRO: Falha durante a sincronização: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# --- Loop Principal ---
if __name__ == '__main__':
    log(f"Serviço de Sincronização iniciado. O trabalho será executado a cada {SYNC_INTERVAL} minuto(s).")
    run_sync()
    schedule.every(SYNC_INTERVAL).minutes.do(run_sync)
    while True:
        schedule.run_pending()
        time.sleep(1)
