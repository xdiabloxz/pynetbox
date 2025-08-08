import os
import pynetbox
from flask import Flask, Response, request

app = Flask(__name__)

NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
# Lê a lista de IPs permitidos, que será uma string separada por vírgulas
ALLOWED_IPS_STR = os.environ.get('ALLOWED_IPS') 

if not NETBOX_URL or not NETBOX_TOKEN:
    raise ValueError("As variáveis de ambiente NETBOX_URL e NETBOX_TOKEN são obrigatórias.")

# Converte a string de IPs em uma lista, se ela existir
ALLOWED_IPS_LIST = [ip.strip() for ip in ALLOWED_IPS_STR.split(',')] if ALLOWED_IPS_STR else []

nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)

if "https://" in NETBOX_URL:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    nb.http_session = session

@app.route('/devices.csv')
def get_devices_for_oxidized():
    # --- LÓGICA DE SEGURANÇA: WHITELIST DE IP ---
    # Pega o IP real do cliente, mesmo atrás de um proxy
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr).split(',')[0].strip()

    # Se a lista de IPs permitidos não estiver vazia, verifica se o cliente está nela
    if ALLOWED_IPS_LIST and client_ip not in ALLOWED_IPS_LIST:
        print(f"ACESSO NEGADO para o IP: {client_ip}. IPs permitidos: {ALLOWED_IPS_LIST}")
        return Response(f"Acesso Proibido para o IP {client_ip}", status=403)

    output_lines = []
    try:
        devices = nb.dcim.devices.filter(status='active')
        
        for device in devices:
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            port = int(device.custom_fields['ssh_port'])
            line = (
                f"{device.primary_ip4.address.split('/')[0]}:"
                f"{device.platform.slug}:"
                f"{device.custom_fields['oxidized_username']}:"
                f"{device.custom_fields['oxidized_password']}:"
                f"{port}"
            )
            output_lines.append(line)
            
    except pynetbox.RequestError as e:
        print(f"Erro ao conectar com a API do NetBox: {e.request.method} {e.request.url} - {e}")
        return Response("Erro ao buscar dados do NetBox.", status=500)

    return Response('\n'.join(output_lines), mimetype='text/plain')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
