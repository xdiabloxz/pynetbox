import os
import pynetbox
import psycopg2
import time
import schedule
from datetime import datetime
import requests
import traceback # Importa a biblioteca para logs de erro detalhados

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
    # ... (função igual à anterior) ...
    if not OXIDized_URL:
        # ...
    # ...

def run_sync():
    log("INICIANDO ciclo de sincronização...")
    
    # ... (conexões com NetBox e DB são iguais) ...
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
    try:
        conn = psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS)
        cur = conn.cursor()
    except Exception as e:
        log(f"ERRO: Falha ao conectar com o PostgreSQL: {e}"); return

    # ... (criação/ajuste da tabela é igual) ...
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (...);
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS ...;
    """)
    conn.commit()

    try:
        db_devices_data = {}
        cur.execute("SELECT ip, name, model, port, username, password, enable, input, device_group FROM devices;")
        for row in cur.fetchall():
            db_devices_data[row[0]] = (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8])

        netbox_devices_data = {}
        devices_to_insert = []
        log("Processando dispositivos do NetBox para comparação...")
        for device in devices_from_netbox:
            # --- DEBUG DETALHADO ---
            log(f"  - Processando: {device.name}")
            if not all([...]): # Mesma verificação de antes
                log(f"    -> PULADO: Faltam campos essenciais.")
                continue

            ip_address = device.primary_ip4.address.split('/')[0]
            
            use_enable = device.custom_fields.get('oxidized_use_enable', False)
            enable_value = device.custom_fields.get('enable_password') or 'true' if use_enable else None
            input_method = device.custom_fields.get('oxidized_input')
            device_group = device.role.slug if device.role else 'default'
            
            # Constrói a tupla de dados
            device_tuple = (
                device.name, ip_address, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_value, input_method, device_group
            )
            devices_to_insert.append(device_tuple)
            netbox_devices_data[ip_address] = device_tuple[1:] # Compara a partir do nome

        if db_devices_data != netbox_devices_data:
            log("Mudança detectada. Sincronizando...")
            cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
            insert_query = "INSERT INTO devices (name, ip, model, port, username, password, enable, input, device_group) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cur.executemany(insert_query, devices_to_insert)
            conn.commit()
            log(f"Sincronização CONCLUÍDA. {len(devices_to_insert)} registros inseridos.")
            trigger_oxidized_reload()
        else:
            log("Nenhuma mudança encontrada.")

    except Exception as e:
        # --- DEBUG DE ERRO MELHORADO ---
        log(f"ERRO CRÍTICO durante a sincronização: {e}")
        log("--- INÍCIO DO TRACEBACK ---")
        traceback.print_exc() # Imprime o erro detalhado com a linha exata
        log("--- FIM DO TRACEBACK ---")
        conn.rollback()
    finally:
        cur.close(); conn.close()

# ... (Loop Principal é igual) ...
