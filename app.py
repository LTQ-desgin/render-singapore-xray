import json
import os
import re
import signal
import subprocess
import time
import uuid
from pathlib import Path


def generate(directory=Path('/tmp')):
    client_id = str(uuid.UUID(os.environ['VLESS_UUID']))
    ws_token = os.environ['WS_TOKEN']
    sub_token = os.environ['SUB_TOKEN']
    host = os.environ['RENDER_EXTERNAL_HOSTNAME']
    port = int(os.environ.get('PORT', '8080'))
    for token in (ws_token, sub_token):
        if not re.fullmatch(r'[a-f0-9]{32,64}', token):
            raise ValueError('Invalid path token')
    if not re.fullmatch(r'[a-zA-Z0-9.-]+', host) or not 1024 <= port <= 65535:
        raise ValueError('Invalid hostname or port')
    ws_path = '/ws/' + ws_token
    private_ips = ['0.0.0.0/8', '10.0.0.0/8', '100.64.0.0/10', '127.0.0.0/8',
                   '169.254.0.0/16', '172.16.0.0/12', '192.168.0.0/16',
                   '224.0.0.0/4', '240.0.0.0/4', '::/128', '::1/128',
                   'fc00::/7', 'fe80::/10', 'ff00::/8']
    xray = {
        'log': {'loglevel': 'warning', 'access': 'none'},
        'inbounds': [{'listen': '127.0.0.1', 'port': 3000, 'protocol': 'vless',
                      'settings': {'clients': [{'id': client_id}], 'decryption': 'none'},
                      'streamSettings': {'network': 'ws', 'security': 'none',
                                         'wsSettings': {'path': ws_path}}}],
        'outbounds': [{'protocol': 'freedom', 'tag': 'direct',
                       'settings': {'domainStrategy': 'UseIP'}},
                      {'protocol': 'blackhole', 'tag': 'block'}],
        'routing': {'domainStrategy': 'IPOnDemand', 'rules': [
            {'type': 'field', 'ip': private_ips, 'outboundTag': 'block'},
            {'type': 'field', 'port': '25', 'outboundTag': 'block'}]}}
    node = {'name': 'Render-Singapore', 'type': 'vless', 'server': host,
            'port': 443, 'uuid': client_id, 'network': 'ws', 'tls': True,
            'servername': host, 'skip-cert-verify': False, 'alpn': ['http/1.1'],
            'ws-opts': {'path': ws_path, 'headers': {'Host': host}}}
    clash = {'mixed-port': 7897, 'allow-lan': False, 'bind-address': '127.0.0.1',
             'mode': 'rule', 'log-level': 'warning', 'ipv6': False,
             'proxies': [node],
             'proxy-groups': [{'name': 'PROXY', 'type': 'select',
                               'proxies': ['Render-Singapore', 'DIRECT']}],
             'rules': ['IP-CIDR,127.0.0.0/8,DIRECT,no-resolve',
                       'IP-CIDR,10.0.0.0/8,DIRECT,no-resolve',
                       'IP-CIDR,172.16.0.0/12,DIRECT,no-resolve',
                       'IP-CIDR,192.168.0.0/16,DIRECT,no-resolve', 'MATCH,PROXY']}
    nginx = '''pid /tmp/nginx.pid;
worker_processes 1;
error_log /dev/stderr warn;
events { worker_connections 256; }
http {
    access_log off;
    client_body_temp_path /tmp/nginx-client;
    proxy_temp_path /tmp/nginx-proxy;
    fastcgi_temp_path /tmp/nginx-fastcgi;
    uwsgi_temp_path /tmp/nginx-uwsgi;
    scgi_temp_path /tmp/nginx-scgi;
    server {
        listen 0.0.0.0:PORT;
        location = /healthz { return 200 'ok'; }
        location = /SUB_TOKEN/clash.yaml {
            alias /tmp/clash.yaml;
            default_type application/yaml;
            add_header Cache-Control 'no-store' always;
            add_header X-Content-Type-Options 'nosniff' always;
        }
        location = WS_PATH {
            proxy_pass http://127.0.0.1:3000;
            proxy_http_version 1.1;
            proxy_set_header Upgrade $http_upgrade;
            proxy_set_header Connection 'upgrade';
            proxy_set_header Host $host;
            proxy_read_timeout 3600s;
            proxy_send_timeout 3600s;
            proxy_buffering off;
        }
        location / { return 404; }
    }
}
'''.replace('PORT', str(port)).replace('SUB_TOKEN', sub_token).replace('WS_PATH', ws_path)
    for filename, content in [('xray.json', json.dumps(xray)),
                              ('clash.yaml', json.dumps(clash, ensure_ascii=False, indent=2)),
                              ('nginx.conf', nginx)]:
        path = directory / filename
        path.write_text(content, encoding='utf-8')
        path.chmod(0o600)


def main():
    os.umask(0o077)
    generate()
    subprocess.run(['xray', 'run', '-test', '-config', '/tmp/xray.json'], check=True)
    subprocess.run(['nginx', '-t', '-c', '/tmp/nginx.conf'], check=True)
    processes = []

    def stop(*_):
        for process in processes:
            if process.poll() is None:
                process.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    try:
        processes.append(subprocess.Popen(['xray', 'run', '-config', '/tmp/xray.json']))
        processes.append(subprocess.Popen(['nginx', '-c', '/tmp/nginx.conf', '-g', 'daemon off;']))
        while all(process.poll() is None for process in processes):
            time.sleep(0.2)
        codes = [process.poll() for process in processes]
    finally:
        stop()
        for process in processes:
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    raise SystemExit(next((code for code in codes if code), 0))


if __name__ == '__main__':
    main()
