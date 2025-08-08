import os
import pynetbox
from flask import Flask, Response, request
import ipaddress

app = Flask(__name__)

NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
ALLOWED_IPS_STR = os.environ.get('ALLOWED_IPS') 

if not NETBOX_URL or not NETBOX_TOKEN:
    raise ValueError("As variáveis de ambiente NETBOX_URL e NETBOX_TOKEN são obrigatórias.")

ALLOWED_ENTRIES = [entry.strip() for entry in ALLOWED_IPS_STR.split(',')] if ALLOWED_IPS_STR else []

nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)

if "https://" in NETBOX_URL:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    nb.http_session = session

def is_ip_allowed(remote_ip):
    if not ALLOWED_ENTRIES:
        return True
    try:
        ip_to_check = ipaddress.ip_address(remote_ip)
        for entry in ALLOWED_ENTRIES:
            try:
                if "/" in entry:
                    if ip_to_check in ipaddress.ip_network(entry, strict=False):
                        return True
                else:
                    if ip_to_check == ipaddress.ip_address(entry):
                        return True
            except ValueError:
                print(f"AVISO: Ignorando entrada inválida na lista ALLOWED_IPS: '{entry}'")
                continue
    except ValueError:
        print(f"AVISO: Endereço de IP remoto inválido recebido: '{remote_ip}'")
        return False
    return False

@app.route('/devices.csv')
def get_devices_for_oxidized():
    client_ip = request.headers.get('X-Forwarded-for', request.remote_addr).split(',')[0].strip()
    if not is_ip_allowed(client_ip):
        print(f"ACESSO NEGADO para o IP: {client_ip}. Não está na lista de permissões: {ALLOWED_ENTRIES}")
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
            
            # --- CORREÇÃO FINAL E DEFINITIVA AQUI ---
            # Voltamos ao método original de tratar o IP como texto e dividir pela '/'
            # para remover a máscara. Esta é a forma correta para a sua versão.
            ip_address = device.primary_ip4.address.split('/')[0]
            port = int(device.custom_fields['ssh_port'])
            
            line = (
                f"{ip_address}:"
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
