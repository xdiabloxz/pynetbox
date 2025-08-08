import os
import pynetbox
from flask import Flask, Response, request # <--- MUDANÇA: Adicionado 'request'

# Inicializa a aplicação web
app = Flask(__name__)

# Lê as variáveis de ambiente para segurança
NETBOX_URL = os.environ.get('NETBOX_URL')
NETBOX_TOKEN = os.environ.get('NETBOX_TOKEN')
ALLOWED_IP = os.environ.get('ALLOWED_IP') # <--- MUDANÇA: Nova variável para o IP do Oxidized

# Validação inicial
if not NETBOX_URL or not NETBOX_TOKEN:
    raise ValueError("As variáveis de ambiente NETBOX_URL e NETBOX_TOKEN são obrigatórias.")

# Conecta-se à API do NetBox
nb = pynetbox.api(url=NETBOX_URL, token=NETBOX_TOKEN)

# --- CORREÇÃO DO BUG DE SINTAXE ABAIXO ---
# O erro de aspas duplas extras foi corrigido.
if "https://" not in NETBOX_URL:
    import requests
    from requests.packages.urllib3.exceptions import InsecureRequestWarning
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    session = requests.Session()
    session.verify = False
    nb.http_session = session

# Cria a rota/página que o Oxidized irá acessar
@app.route('/devices.csv')
def get_devices_for_oxidized():
    # --- MUDANÇA: VERIFICAÇÃO DE SEGURANÇA POR IP ---
    # Se a variável ALLOWED_IP foi definida, só permite o acesso daquele IP.
    if ALLOWED_IP and request.remote_addr != ALLOWED_IP:
        print(f"Acesso negado para o IP: {request.remote_addr}. IP permitido: {ALLOWED_IP}")
        return Response("Acesso Proibido", status=403)

    output_lines = []
    try:
        # Busca todos os dispositivos com status 'active'
        devices = nb.dcim.devices.filter(status='active')
        
        for device in devices:
            # Pula o dispositivo se algum campo essencial estiver faltando
            if not all([device.primary_ip4, device.platform, 
                        device.custom_fields.get('oxidized_username'),
                        device.custom_fields.get('oxidized_password'),
                        device.custom_fields.get('ssh_port')]):
                continue

            # Monta a linha no formato que o Oxidized espera
            line = (
                f"{device.primary_ip4.address.split('/')[0]}:"
                f"{device.platform.slug}:"
                f"{device.custom_fields['oxidized_username']}:"
                f"{device.custom_fields['oxidized_password']}:"
                f"{device.custom_fields['ssh_port']}"
            )
            output_lines.append(line)
            
    except pynetbox.RequestError as e:
        print(f"Erro ao conectar com a API do NetBox: {e.request.method} {e.request.url} - {e}")
        return Response("Erro ao buscar dados do NetBox.", status=500)

    # Junta todas as linhas com uma quebra de linha e retorna como texto puro
    return Response('\n'.join(output_lines), mimetype='text/plain')

# Roda a aplicação na porta 5000, acessível por outros contêineres
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
