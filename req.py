import urllib.request, json, urllib.error
import io
import time
import sys

# 1. Esperar o GitHub Actions concluir o build da imagem
print("Verificando status do GitHub Actions...")
while True:
    try:
        req_gh = urllib.request.Request('https://api.github.com/repos/cristhian-sancore/graficarapida/actions/runs?per_page=1')
        req_gh.add_header('User-Agent', 'Mozilla/5.0')
        res_gh = urllib.request.urlopen(req_gh)
        data = json.loads(res_gh.read().decode('utf-8'))
        
        runs = data.get('workflow_runs', [])
        if not runs:
            print("Nenhum workflow encontrado, prosseguindo...")
            break
            
        latest_run = runs[0]
        status = latest_run.get('status')
        conclusion = latest_run.get('conclusion')
        
        if status == 'completed':
            if conclusion == 'success':
                print(f"Workflow {latest_run['id']} concluído com sucesso!")
            else:
                print(f"AVISO: Workflow {latest_run['id']} terminou com status: {conclusion}")
            break
        else:
            print(f"Workflow {latest_run['id']} em andamento (status: {status}). Aguardando 15 segundos...")
            time.sleep(15)
    except Exception as e:
        print("Erro ao verificar GitHub API, ignorando e prosseguindo:", e)
        break

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

