#!/usr/bin/env python3
"""Extrator de nomes (spaCy, modelo português): propostas de pessoas, lugares e instituições.

Fase 1 (sem alterar nada):  python3 extrator_nomes.py            -> grava /out/extrator_nomes.json
Fase 2 (gravar propostas):  python3 extrator_nomes.py --aplicar  -> cria termos e ligações no Directus
                            (estado «proposta», origem «extrator»), sem tocar no que já existe.

Só propõe nomes que ainda não são termos e que aparecem em pelo menos MIN_ENTRADAS entradas diferentes.
Corre no servidor, num contentor Python, com a chave de administração (não sai do servidor).
"""
import collections
import html
import json
import os
import re
import sys
import unicodedata
import urllib.request

URL = os.environ.get('DIRECTUS_URL', 'http://127.0.0.1:8055')
TOKEN = open(os.environ.get('TOKEN_FICHEIRO', '/env/operador.token')).read().strip()
SAIDA = os.environ.get('SAIDA', '/out/extrator_nomes.json')
MIN_ENTRADAS = int(os.environ.get('MIN_ENTRADAS', '2'))
TIPO = {'PER': 'pessoa', 'LOC': 'lugar', 'ORG': 'instituicao'}
# palavras que o modelo costuma marcar como nomes mas não interessam como termos
IGNORAR = {'deus', 'nossa senhora', 'sua majestade', 'el-rei', 'santa se', 'sao', 'santo', 'dom', 'senhor', 'cristo',
           'jesus', 'jesus cristo', 'virgem maria', 'europa', 'portugal', 'lisboa', 'madeira', 'ilha da madeira',
           'arquipelago da madeira', 'regiao autonoma da madeira', 'atlantico', 'oceano atlantico'}


def api(metodo, caminho, dados=None):
    corpo = json.dumps(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(URL + caminho, data=corpo, method=metodo,
                                    headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(pedido, timeout=120) as r:
        texto = r.read()
        return json.loads(texto)['data'] if texto else None


def chave(s):
    s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
    return re.sub(r'\s+', ' ', s.lower()).strip()


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', chave(s)).strip('-') or 'termo'


def extrair():
    import spacy
    entradas = api('GET', '/items/entradas?limit=-1&fields=id,slug,corpo&filter[estado][_eq]=publicado')
    termos = api('GET', '/items/palavras_chave?limit=-1&fields=id,termo,variantes')
    conhecidos = set(IGNORAR)
    for t in termos:
        conhecidos.add(chave(re.sub(r'\s*\((concelho|freguesia)\)$', '', t['termo'])))
        for v in (t.get('variantes') or []):
            conhecidos.add(chave(v))
    nlp = spacy.load('pt_core_news_lg', disable=['lemmatizer'])
    nlp.max_length = 3_000_000
    cand = collections.defaultdict(lambda: {'n': 0, 'entradas': {}, 'formas': collections.Counter(), 'rotulo': collections.Counter()})
    textos = [(e['id'], re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', e['corpo'] or '')))) for e in entradas]
    for n, (doc, (eid, _)) in enumerate(zip(nlp.pipe((t for _, t in textos), batch_size=8), textos)):
        for ent in doc.ents:
            if ent.label_ not in TIPO:
                continue
            texto = re.sub(r'\s+', ' ', ent.text).strip(' .,;:()«»"“”\'')
            if len(texto) < 4 or not texto[0].isupper() or re.search(r'\d', texto):
                continue
            if ent.label_ == 'PER' and len(texto.split()) < 2:
                continue
            k = chave(texto)
            if k in conhecidos:
                continue
            c = cand[k]
            c['n'] += 1
            c['formas'][texto] += 1
            c['rotulo'][ent.label_] += 1
            if eid not in c['entradas']:
                c['entradas'][eid] = ent.sent.text.strip()[:600]
        if n % 100 == 0:
            print(f'{n}/{len(textos)} entradas', flush=True)
    res = []
    for c in cand.values():
        if len(c['entradas']) < MIN_ENTRADAS:
            continue
        res.append({'termo': c['formas'].most_common(1)[0][0], 'tipo': TIPO[c['rotulo'].most_common(1)[0][0]],
                    'ocorrencias': c['n'], 'entradas': c['entradas']})
    res.sort(key=lambda x: -len(x['entradas']))
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump(res, open(SAIDA, 'w'), ensure_ascii=False)
    por_tipo = collections.Counter(r['tipo'] for r in res)
    print(f'{len(res)} candidatos ({dict(por_tipo)}); {sum(len(r["entradas"]) for r in res)} ligações; gravado em {SAIDA}')
    for tipo in ('pessoa', 'lugar', 'instituicao'):
        amostra = [f'{r["termo"]} ({len(r["entradas"])})' for r in res if r['tipo'] == tipo][:15]
        print(tipo, ':', ', '.join(amostra))


def aplicar():
    res = json.load(open(SAIDA))
    existentes = api('GET', '/items/palavras_chave?limit=-1&fields=id,termo,slug')
    por_chave = {chave(t['termo']): t['id'] for t in existentes}
    slugs = {t['slug'] for t in existentes}
    novos = []
    for r in res:
        if chave(r['termo']) in por_chave:
            continue
        s, n = slugify(r['termo']), 2
        base = s
        while s in slugs:
            s, n = f'{base}-{n}', n + 1
        slugs.add(s)
        novos.append((r, {'termo': r['termo'], 'slug': s, 'tipo': r['tipo'], 'estado': 'proposta', 'origem': 'extrator'}))
    for i in range(0, len(novos), 100):
        lote = novos[i:i + 100]
        criados = api('POST', '/items/palavras_chave?fields=id', [x[1] for x in lote])
        for (r, _), c in zip(lote, criados):
            por_chave[chave(r['termo'])] = c['id']
    ligacoes = []
    for r in res:
        pid = por_chave[chave(r['termo'])]
        for eid, frase in r['entradas'].items():
            ligacoes.append({'entradas_id': int(eid), 'palavras_chave_id': pid, 'relevancia': 'referido',
                             'origem': 'extrator', 'estado': 'proposta', 'contexto': frase})
    existentes_lig = api('GET', '/items/entradas_palavras_chave?limit=-1&fields=entradas_id,palavras_chave_id')
    ja = {(l['entradas_id'], l['palavras_chave_id']) for l in existentes_lig}
    ligacoes = [l for l in ligacoes if (l['entradas_id'], l['palavras_chave_id']) not in ja]
    for i in range(0, len(ligacoes), 250):
        api('POST', '/items/entradas_palavras_chave', ligacoes[i:i + 250])
    print(f'{len(novos)} termos novos e {len(ligacoes)} ligações gravados como propostas.')


if __name__ == '__main__':
    aplicar() if '--aplicar' in sys.argv else extrair()
