import urllib.request, json, urllib.error
import io
import time
import sys

import subprocess

# 1. Obter o SHA do commit local
try:
    current_sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    print(f"Commit SHA atual: {current_sha[:7]} ({current_sha})")
except Exception:
    current_sha = None

# 2. Esperar o GitHub Actions concluir o build da imagem correspondente ao commit
print("Verificando status do GitHub Actions...")
while True:
    try:
        req_gh = urllib.request.Request('https://api.github.com/repos/cristhian-sancore/graficarapida/actions/runs?per_page=5')
        req_gh.add_header('User-Agent', 'Mozilla/5.0')
        res_gh = urllib.request.urlopen(req_gh)
        data = json.loads(res_gh.read().decode('utf-8'))
        
        runs = data.get('workflow_runs', [])
        target_run = None
        if current_sha:
            for r in runs:
                if r.get('head_sha') == current_sha:
                    target_run = r
                    break
        elif runs:
            target_run = runs[0]
            
        if not target_run:
            print("Aguardando GitHub registrar o novo workflow para o commit... (10s)")
            time.sleep(10)
            continue
            
        status = target_run.get('status')
        conclusion = target_run.get('conclusion')
        
        if status == 'completed':
            if conclusion == 'success':
                print(f"Workflow {target_run['id']} concluído com sucesso!")
            else:
                print(f"AVISO: Workflow {target_run['id']} terminou com status: {conclusion}")
            break
        else:
            print(f"Workflow {target_run['id']} em andamento (status: {status}). Aguardando 15 segundos...")
            time.sleep(15)
    except Exception as e:
        print("Erro ao verificar GitHub API, aguardando 10s:", e)
        time.sleep(10)

# 2. Atualizar stack no Portainer
with open('docker-compose.portainer.yml', 'r', encoding='utf-8') as f:
    stack_file = f.read()

data=json.dumps({
  'StackFileContent': stack_file,
  'Env': [],
  'Prune': True,
  'PullImage': True
}).encode('utf-8')

req=urllib.request.Request(
    'http://31.220.109.77:9000/api/stacks/5?endpointId=3', 
    data=data, 
    headers={
        'X-API-Key':'ptr_sMXw7zPj+YZ5R2QpH0TlO7VNwK8dKdL2IbgvBSFkK80=', 
        'Content-Type':'application/json'
    }, 
    method='PUT'
)

try:
    print("Enviando comando para o Portainer...")
    res = urllib.request.urlopen(req)
    print("SUCCESS")
    print(res.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print('HTTP ERROR', e.code)
    print(e.read().decode('utf-8'))

