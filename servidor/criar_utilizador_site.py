#!/usr/bin/env python3
"""Cria no Directus o utilizador «Site público (só leitura)» e grava a chave em site.env.

Corre no servidor, como root:  python3 servidor/criar_utilizador_site.py
- Usa a chave de administração em /opt/aprendermadeira/env/operador.token (não sai do servidor).
- O novo utilizador só pode LER entradas publicadas e o que elas precisam (autores, temas, fontes,
  imagens, traduções). Não pode alterar nada, nem ver notas internas, e-mails ou utilizadores.
- A chave nova é gerada aqui e gravada em /opt/aprendermadeira/env/site.env (permissões 600).
Pode correr-se outra vez: reaproveita a política e o papel e gera uma chave nova.
"""
import json
import os
import secrets
import urllib.error
import urllib.parse
import urllib.request

URL = 'http://127.0.0.1:8055'
ADMIN = open('/opt/aprendermadeira/env/operador.token').read().strip()
ENV = '/opt/aprendermadeira/env/site.env'
NOME = 'Site público (só leitura)'
EMAIL = 'site-publico@aprenderamadeira.net'

# Coleção -> (campos que se podem ler, filtro)
LEITURA = {
    'entradas': ([
        'id', 'titulo', 'slug', 'estado', 'tipo', 'origem', 'resumo', 'corpo', 'seculo_inicio', 'seculo_fim',
        'data_inicio', 'data_fim', 'lugares', 'licenca', 'doi', 'data_publicacao', 'data_atualizacao', 'colecao',
        'translations', 'autores', 'categorias', 'palavras_chave', 'imagens', 'relacionadas', 'fontes', 'multimedia',
    ], {'estado': {'_eq': 'publicado'}}),
    'entradas_translations': ([
        'id', 'titulo', 'slug', 'resumo', 'corpo', 'estado_traducao', 'origem_traducao', 'data_revisao',
        'entradas_id', 'languages_code',
    ], None),
    'entradas_autores': (['*'], None),
    'autores': (['id', 'nome', 'nome_citacao', 'slug', 'orcid', 'afiliacao', 'nota_biografica', 'foto', 'falecido'], None),
    'entradas_categorias': (['*'], None),
    'categorias': (['id', 'nome', 'slug', 'pai', 'descricao', 'ordem', 'subtemas', 'translations'], None),
    'categorias_translations': (['*'], None),
    'entradas_imagens': (['*'], None),
    'entradas_relacionadas': (['*'], None),
    'fontes': (['*'], None),
    'multimedia': (['*'], None),
    'languages': (['*'], None),
    'directus_files': (['id', 'title', 'description', 'width', 'height', 'type', 'folder', 'filename_download', 'filesize'], None),
    'directus_folders': (['id', 'name', 'parent'], None),
}


def api(metodo, caminho, dados=None):
    corpo = json.dumps(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(URL + caminho, data=corpo, method=metodo, headers={
        'Authorization': 'Bearer ' + ADMIN, 'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(pedido) as r:
            texto = r.read()
            return json.loads(texto)['data'] if texto else None
    except urllib.error.HTTPError as e:
        raise SystemExit(f'ERRO {e.code} em {metodo} {caminho}: {e.read().decode()[:300]}')


def um(caminho):
    dados = api('GET', caminho)
    return dados[0] if dados else None


q = urllib.parse.quote
politica = um(f'/policies?filter[name][_eq]={q(NOME)}&fields=id')
if not politica:
    politica = api('POST', '/policies', {
        'name': NOME, 'icon': 'public', 'app_access': False, 'admin_access': False, 'enforce_tfa': False,
        'description': 'Só leitura das entradas publicadas, para gerar o site público.'})
    print('Política criada')
pid = politica['id']

# Permissões: apaga as antigas desta política e cria-as de novo (assim o script pode repetir-se).
antigas = api('GET', f'/permissions?filter[policy][_eq]={pid}&fields=id&limit=-1') or []
if antigas:
    api('DELETE', '/permissions', [p['id'] for p in antigas])
api('POST', '/permissions', [
    {'policy': pid, 'collection': c, 'action': 'read', 'fields': campos,
     'permissions': filtro or {}, 'validation': None, 'presets': None}
    for c, (campos, filtro) in LEITURA.items()])
print(f'{len(LEITURA)} permissões de leitura')

papel = um(f'/roles?filter[name][_eq]={q(NOME)}&fields=id')
if not papel:
    papel = api('POST', '/roles', {'name': NOME, 'icon': 'public', 'description': 'Gera o site público (só leitura).'})
    print('Papel criado')
rid = papel['id']
if not um(f'/access?filter[role][_eq]={rid}&filter[policy][_eq]={pid}&fields=id'):
    api('POST', '/access', {'role': rid, 'policy': pid})

chave = secrets.token_urlsafe(36)
utilizador = um(f'/users?filter[email][_eq]={q(EMAIL)}&fields=id')
if utilizador:
    api('PATCH', f"/users/{utilizador['id']}", {'token': chave, 'role': rid, 'status': 'active'})
    print('Utilizador atualizado (chave nova)')
else:
    api('POST', '/users', {'first_name': 'Site público', 'last_name': '(só leitura)', 'email': EMAIL,
                           'role': rid, 'status': 'active', 'token': chave})
    print('Utilizador criado')

os.makedirs(os.path.dirname(ENV), exist_ok=True)
fd = os.open(ENV, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, 'w') as f:
    f.write('\n'.join([
        'SITE_URL=https://teste.aprenderamadeira.net',
        'DIRECTUS_URL=http://127.0.0.1:8055',
        f'DIRECTUS_TOKEN={chave}',
        'IMAGENS_LOCAIS=1',
        'IMAGENS_DIR=/persistente/imagens',
        'CITACOES_FICHEIRO=/persistente/citacoes.json',
        'NAO_INDEXAR=1',
    ]) + '\n')
os.chmod(ENV, 0o600)


# Verificação com a chave nova
def com_chave(caminho):
    pedido = urllib.request.Request(URL + caminho, headers={'Authorization': 'Bearer ' + chave})
    try:
        with urllib.request.urlopen(pedido) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None


estado, dados = com_chave('/items/entradas?aggregate[count]=id')
print('Entradas publicadas visíveis:', dados['data'][0]['count']['id'] if dados else f'erro {estado}')
estado, _ = com_chave('/items/entradas?limit=1&fields=notas_editoriais')
print('Notas internas bloqueadas:', 'sim' if estado == 403 else f'NAO (resposta {estado})')
estado, _ = com_chave('/users?limit=1')
print('Utilizadores bloqueados:', 'sim' if estado == 403 else f'NAO (resposta {estado})')
print('Chave gravada em', ENV)
