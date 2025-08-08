import os
import pynetbox
import psycopg2
import time
import schedule

# --- CONFIGURAÇÕES (lidas do ambiente) ---
NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
DB_HOST = os.environ.get('DB_HOST')
DB_NAME = os.environ.get('DB_NAME')
DB_USER = os.environ.get('DB_USER')
DB_PASS = os.environ.get('DB_PASS')

def run_sync():
    print("Iniciando a sincronização de dispositivos do NetBox para o PostgreSQL...")
    
    # 1. Conectar ao NetBox
    try:
        nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)
        if "https://" in NETBOX_URL:
            import requests
            session = requests.Session()
            session.verify = False
            nb.http_session = session
        
        devices_from_netbox = nb.dcim.devices.filter(status='active')
        print(f"Encontrados {len(devices_from_netbox)} dispositivos ativos no NetBox.")
    except Exception as e:
        print(f"ERRO: Falha ao conectar ou buscar dados do NetBox: {e}")
        return

    # 2. Conectar ao PostgreSQL
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            dbname=DB_NAME,
            user=DB_USER,
            password=DB_PASS
        )
        cur = conn.cursor()
    except Exception as e:
        print(f"ERRO: Falha ao conectar com o PostgreSQL: {e}")
        return

    # 3. Criar a tabela se ela não existir
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            ip TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL,
            port INTEGER NOT NULL,
            username TEXT NOT NULL,
            password TEXT NOT NULL
        );
    """)

    # 4. Sincronizar dados (apaga tudo e insere a lista fresca do NetBox)
    try:
        device_list_to_insert = []
        for device in devices_from_netbox:
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            ip_address = device.primary_ip4.address.split('/')[0]
            
            device_list_to_insert.append((
                device.name,
                ip_address,
                device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password']
            ))

        # Executa a sincronização dentro de uma transação
        cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
        print(f"Tabela 'devices' limpa. Inserindo {len(device_list_to_insert)} novos registros...")
        
        insert_query = "INSERT INTO devices (name, ip, model, port, username, password) VALUES (%s, %s, %s, %s, %s, %s)"
        cur.executemany(insert_query, device_list_to_insert)

        conn.commit()
        print("Sincronização concluída com sucesso!")

    except Exception as e:
        print(f"ERRO: Falha durante a sincronização: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()

# --- Loop Principal ---
# Roda a sincronização imediatamente ao iniciar, e depois a cada 5 minutos.
if __name__ == '__main__':
    run_sync()
    schedule.every(5).minutes.do(run_sync)
    print("Agendador iniciado. Próxima sincronização em 5 minutos.")
    while True:
        schedule.run_pending()
        time.sleep(1)
