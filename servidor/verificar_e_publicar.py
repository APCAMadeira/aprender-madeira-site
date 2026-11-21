#!/usr/bin/env python3
"""Reconstrói o site só quando alguma coisa mudou. Corre a cada 15 minutos (cron).

Compara uma «assinatura» do conteúdo (última alteração e número de registos no Directus)
e a última versão do código no GitHub com a da publicação anterior. Se nada mudou, não faz nada.
"""
import json
import os
import subprocess
import sys
import urllib.request

URL = 'http://127.0.0.1:8055'
TOKEN = open('/opt/aprendermadeira/env/operador.token').read().strip()
SITE = '/opt/aprendermadeira/site'
ESTADO = '/opt/aprendermadeira/site-dados/ultima-assinatura.txt'
COLECOES = ['entradas', 'entradas_translations', 'entradas_imagens', 'entradas_categorias',
            'entradas_autores', 'autores', 'categorias', 'fontes']


def resumo(colecao):
    pedido = urllib.request.Request(
        f'{URL}/items/{colecao}?aggregate[max]=date_updated&aggregate[count]=id',
        headers={'Authorization': 'Bearer ' + TOKEN})
    try:
        with urllib.request.urlopen(pedido, timeout=30) as r:
            return json.dumps(json.loads(r.read())['data'], sort_keys=True)
    except Exception:
        try:  # coleções sem date_updated: só a contagem
            pedido = urllib.request.Request(f'{URL}/items/{colecao}?aggregate[count]=id',
                                            headers={'Authorization': 'Bearer ' + TOKEN})
            with urllib.request.urlopen(pedido, timeout=30) as r:
                return json.dumps(json.loads(r.read())['data'], sort_keys=True)
        except Exception:
            return f'{colecao}:sem-resposta'


codigo = subprocess.run(['git', '-C', SITE, 'ls-remote', 'origin', 'main'],
                        capture_output=True, text=True).stdout.split('\t')[0]
assinatura = codigo + '|' + '|'.join(resumo(c) for c in COLECOES)
anterior = open(ESTADO).read() if os.path.exists(ESTADO) else ''
if assinatura == anterior:
    sys.exit(0)

resultado = subprocess.run(['bash', f'{SITE}/servidor/publicar.sh'])
if resultado.returncode == 0:
    os.makedirs(os.path.dirname(ESTADO), exist_ok=True)
    with open(ESTADO, 'w') as f:
        f.write(assinatura)
sys.exit(resultado.returncode)
