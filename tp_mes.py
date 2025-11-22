import requests
import json
import time
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURAÇÃO ---
GITHUB_TOKEN = "INSIRA O TOKEN AQUI"  
REPO_NAME = "microsoft/vscode"
LABEL = "bug"
DATA_CORTE = "2021-01-01"
META_ITENS = 50

headers = {
    "Accept": "application/vnd.github.v3+json",
    "Authorization": f"token {GITHUB_TOKEN}"
}

# --- FUNÇÃO DE BUSCA COM SSL DESATIVADO ---
def buscar_prs_pagina(pagina):
    url = "https://api.github.com/search/issues"
    query = f"repo:{REPO_NAME} is:pr is:merged label:{LABEL} created:<{DATA_CORTE}"
    params = {
        "q": query, "per_page": 100, "page": pagina,
        "sort": "created", "order": "asc"
    }
    try:
        # ADICIONADO: verify=False
        response = requests.get(url, headers=headers, params=params, verify=False)
        return response.json().get('items', [])
    except Exception as e:
        print(f"Erro busca: {e}")
        return []

def obter_detalhes_pr(pr_url_api):
    resp = requests.get(pr_url_api, headers=headers, verify=False)
    if resp.status_code == 200:
        return resp.json()
    return None

def obter_arquivos_alterados(pr_number):
    url = f"https://api.github.com/repos/{REPO_NAME}/pulls/{pr_number}/files"
    resp = requests.get(url, headers=headers, verify=False)
    return resp.json() if resp.status_code == 200 else []

def baixar_arquivo_historico(blob_url):
    """
    Baixa o conteúdo cru do arquivo no estado 'anterior' (raw).
    """
    try:
        resp = requests.get(blob_url, headers=headers, verify=False)
        if resp.status_code == 200:
            return resp.text
    except Exception as e:
        print(f"Erro ao baixar raw: {e}")
    return None

def coletar_dataset_com_contexto():
    dataset = []
    pagina_atual = 1
    
    print(f"🚀 Iniciando mineração profunda (Contexto Completo). Meta: {META_ITENS} itens.")
    
    while len(dataset) < META_ITENS:
        items = buscar_prs_pagina(pagina_atual)
        if not items: 
            print("⚠️ Fim dos resultados na busca ou erro na página.")
            break
            
        for item in items:
            if len(dataset) >= META_ITENS: break
            
            pr_number = item.get('number')
            
            url_pr_especifica = f"https://api.github.com/repos/{REPO_NAME}/pulls/{pr_number}"
            
            pr_details = obter_detalhes_pr(url_pr_especifica)
            
            if not pr_details or 'base' not in pr_details: 
                print(f"⚠️ Pular PR #{pr_number}: Não foi possível pegar detalhes do Base SHA.")
                continue
            
            base_sha = pr_details['base']['sha']            
            files = obter_arquivos_alterados(pr_number)
            
            # Filtros de Qualidade
            if len(files) != 1: continue
            arquivo = files[0]
            filename = arquivo.get('filename', '')
            
            if not (filename.endswith('.ts') or filename.endswith('.js')): continue
            
            # Construção da URL Raw histórica
            raw_url = f"https://raw.githubusercontent.com/{REPO_NAME}/{base_sha}/{filename}"
            
            conteudo_completo = baixar_arquivo_historico(raw_url)
            
            if not conteudo_completo:
                print(f"⚠️ Falha ao baixar arquivo histórico: {filename}")
                continue
                
            # Filtro: Ignorar arquivos gigantes (acima de 1000 linhas)
            if len(conteudo_completo.split('\n')) > 1000:
                continue

            entrada = {
                "id": pr_number,
                "url": item.get('html_url'),
                "arquivo_caminho": filename,
                "descricao_bug": item.get('body'),
                "contexto": {
                    "codigo_completo_bugado": conteudo_completo,
                    "linguagem": filename.split('.')[-1],
                    "total_linhas": len(conteudo_completo.split('\n'))
                },
                "solucao_humana": {
                    "patch_diff": arquivo.get('patch'),
                    "apenas_linhas_adicionadas": [l[1:] for l in arquivo.get('patch', '').split('\n') if l.startswith('+')]
                }
            }
            
            dataset.append(entrada)
            print(f"✅ PR #{pr_number} coletado | Linhas: {entrada['contexto']['total_linhas']}")
            time.sleep(0.5)
            
        pagina_atual += 1
        
    return dataset

# --- EXECUÇÃO ---
dados = coletar_dataset_com_contexto()

if dados:
    with open("dataset_vscode_full_context.json", "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=4, ensure_ascii=False)
    print(f"\n🎉 Sucesso! Dataset salvo com CONTEXTO COMPLETO.")