import os
import pynetbox
import psycopg2
import time
import schedule
from datetime import datetime

# ... (início do script é igual) ...
def run_sync():
    log("INICIANDO ciclo de sincronização...")
    # ... (conexão com NetBox e DB é igual) ...

    # 3. Criar/Ajustar a tabela para incluir a coluna 'input'
    cur.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id SERIAL PRIMARY KEY, name TEXT NOT NULL, ip TEXT NOT NULL UNIQUE,
            model TEXT NOT NULL, port INTEGER NOT NULL, username TEXT NOT NULL,
            password TEXT NOT NULL, enable TEXT, input TEXT
        );
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS enable TEXT;
        ALTER TABLE devices ADD COLUMN IF NOT EXISTS input TEXT;
    """)

    # 4. Sincronizar dados, incluindo o método de acesso (input)
    try:
        device_list_to_insert = []
        for device in devices_from_netbox:
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            ip_address = device.primary_ip4.address.split('/')[0]
            enable_password = device.custom_fields.get('enable_password')
            # Pega o valor do novo campo 'input', se não existir, usa 'None' (nulo)
            input_method = device.custom_fields.get('oxidized_input')

            device_list_to_insert.append((
                device.name, ip_address, device.platform.slug,
                int(device.custom_fields['ssh_port']),
                device.custom_fields['oxidized_username'],
                device.custom_fields['oxidized_password'],
                enable_password, input_method
            ))

        cur.execute("TRUNCATE TABLE devices RESTART IDENTITY;")
        log(f"Tabela 'devices' limpa. Inserindo {len(device_list_to_insert)} novos registros...")
        
        insert_query = "INSERT INTO devices (name, ip, model, port, username, password, enable, input) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
        cur.executemany(insert_query, device_list_to_insert)

        conn.commit()
        log("Sincronização CONCLUÍDA com sucesso!")
    # ... (resto do script e do loop principal é igual) ...
