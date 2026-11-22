#!/usr/bin/env python3
"""Extrator de nomes (spaCy, modelo português): propostas de pessoas, lugares e instituições.

Fase 1 (sem alterar nada):  python3 extrator_nomes.py            -> grava /out/extrator_nomes.json
                            (a leitura com o spaCy fica guardada em /out/entidades_brutas.json;
                             --refazer obriga a ler tudo outra vez)
Fase 2 (gravar propostas):  python3 extrator_nomes.py --aplicar  -> cria termos e ligações no Directus
                            (estado «proposta», origem «extrator»), sem tocar no que já existe.

Só propõe nomes que ainda não são termos e que aparecem em pelo menos MIN_ENTRADAS entradas diferentes.
Antes da leitura tira do texto as legendas das imagens e as citações bibliográficas entre parênteses,
para não confundir autores citados e créditos de fotografias com assuntos das entradas.
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
BRUTAS = os.environ.get('BRUTAS', '/out/entidades_brutas.json')
MIN_ENTRADAS = int(os.environ.get('MIN_ENTRADAS', '5'))
TIPO = {'PER': 'pessoa', 'LOC': 'lugar', 'ORG': 'instituicao'}
# nomes demasiado gerais para servirem de palavra-chave
IGNORAR = {'deus', 'nossa senhora', 'sua majestade', 'el-rei', 'santa se', 'cristo', 'jesus', 'jesus cristo',
           'virgem maria', 'europa', 'portugal', 'lisboa', 'madeira', 'ilha da madeira', 'arquipelago da madeira',
           'regiao autonoma da madeira', 'atlantico', 'oceano atlantico', 'mundo', 'reino', 'governo', 'igreja',
           'festa', 'junta', 'assembleia geral', 'decreto legislativo regional'}
# ruas e largos: são lugares, mesmo quando o modelo os lê como pessoas; a abreviatura passa a extenso
VIAS = {'R.': 'Rua', 'Lg.': 'Largo', 'Av.': 'Avenida', 'Trav.': 'Travessa', 'Calç.': 'Calçada'}
VIA = re.compile(r'^(R\.|Rua|Lg\.|Largo|Av\.|Avenida|Trav\.|Travessa|Calç\.|Calçada|Caminho|Beco|Praça) ')
# formas abreviadas e por extenso que contam como a mesma (S. Jorge = São Jorge; D. Manuel = Dom Manuel)
ABREV = {'s': 's', 'sao': 's', 'santo': 's', 'santa': 's', 'sto': 's', 'sta': 's', 's.to': 's', 's.ta': 's',
         'd': 'd', 'dom': 'd', 'dona': 'd', 'fr': 'fr', 'frei': 'fr', 'pe': 'pe', 'padre': 'pe', 'dr': 'dr',
         'doutor': 'dr', 'n': 'n', 'nossa': 'n', 'sr': 'sr', 'sra': 'sr', 'senhor': 'sr', 'senhora': 'sr'}
CREDITO = re.compile(r'\b(Arqui?\.|Arquivo|Fot\.|Foto|Fotografia|Col\.|Coleção|Colecção|Créditos?)\b')


def api(metodo, caminho, dados=None):
    corpo = json.dumps(dados).encode() if dados is not None else None
    pedido = urllib.request.Request(URL + caminho, data=corpo, method=metodo,
                                    headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json'})
    with urllib.request.urlopen(pedido, timeout=120) as r:
        texto = r.read()
        return json.loads(texto)['data'] if texto else None


def sem_acentos(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')


def chave(s):
    """Forma de comparação: sem acentos, minúsculas, abreviaturas uniformizadas."""
    palavras = re.findall(r"[a-z0-9]+(?:\.(?:to|ta))?", sem_acentos(s).lower().replace('-', ' '))
    return ' '.join(ABREV.get(p, p) for p in palavras)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', sem_acentos(s).lower()).strip('-') or 'termo'


def texto_limpo(corpo):
    """HTML -> texto, sem legendas de imagens nem citações bibliográficas."""
    corpo = re.sub(r'(?is)<figure.*?</figure>|<figcaption.*?</figcaption>', ' ', corpo or '')
    partes, anterior_tinha_imagem = [], False
    for p in re.split(r'(?i)</p>', corpo):
        tem_imagem = bool(re.search(r'(?i)<img', p))
        texto = re.sub(r'\s+', ' ', html.unescape(re.sub(r'<[^>]+>', ' ', p))).strip()
        legenda = len(texto) < 300 and (tem_imagem or anterior_tinha_imagem or CREDITO.search(texto)
                                        or re.match(r'(?i)fig(ura)?\.?\s*\d', texto))
        if texto and not legenda:
            partes.append(texto)
        anterior_tinha_imagem = tem_imagem
    texto = '\n'.join(partes)
    # citações do tipo (CARITA, 1991, II, 328) ou (ANTT, Chancelaria…)
    texto = re.sub(r'\([^()]{0,300}?\b[A-ZÁÉÍÓÚÂÊÔÃÕÇ]{3,}\b[^()]{0,300}?\)', ' ', texto)
    return texto


def ler_com_spacy(entradas):
    import spacy
    nlp = spacy.load('pt_core_news_lg', disable=['lemmatizer'])
    nlp.max_length = 3_000_000
    textos = [(e['id'], texto_limpo(e['corpo'])) for e in entradas]
    brutas = []
    for n, (doc, (eid, _)) in enumerate(zip(nlp.pipe((t for _, t in textos), batch_size=8), textos)):
        for ent in doc.ents:
            if ent.label_ in TIPO:
                brutas.append([eid, ent.text, ent.label_, ent.sent.text.strip()[:600]])
        if n % 100 == 0:
            print(f'{n}/{len(textos)} entradas', flush=True)
    json.dump(brutas, open(BRUTAS, 'w'), ensure_ascii=False)
    return brutas


def extrair():
    entradas = api('GET', '/items/entradas?limit=-1&fields=id,slug,corpo&filter[estado][_eq]=publicado')
    termos = api('GET', '/items/palavras_chave?limit=-1&fields=id,termo,variantes')
    autores = api('GET', '/items/autores?limit=-1&fields=nome,nome_citacao')
    conhecidos = {chave(x) for x in IGNORAR}
    # autores do Aprender Madeira: aparecem sobretudo como fonte citada ou crédito de fotografia
    for a in autores:
        for nome in (a.get('nome'), a.get('nome_citacao')):
            if nome:
                conhecidos.add(chave(nome))
    for t in termos:
        conhecidos.add(chave(re.sub(r'\s*\((concelho|freguesia)\)$', '', t['termo'])))
        for v in (t.get('variantes') or []):
            conhecidos.add(chave(v))
    if os.path.exists(BRUTAS) and '--refazer' not in sys.argv:
        brutas = json.load(open(BRUTAS))
        print(f'leitura spaCy reaproveitada de {BRUTAS}')
    else:
        brutas = ler_com_spacy(entradas)
    # quantas vezes cada palavra aparece com minúscula e com maiúscula (para pôr de parte nomes comuns: Estado, Câmara…)
    minus, maius = collections.Counter(), collections.Counter()
    for e in entradas:
        for p in re.findall(r'\w+', texto_limpo(e['corpo'])):
            (maius if p[0].isupper() else minus)[p.lower()] += 1
    cand = collections.defaultdict(lambda: {'n': 0, 'entradas': {}, 'formas': collections.Counter(), 'rotulo': collections.Counter()})
    for eid, texto, rotulo, frase in brutas:
        texto = re.sub(r'\s+', ' ', texto).strip(' .,;:()«»"“”\'')
        palavras = texto.split()
        if len(texto) < 4 or not texto[0].isupper() or re.search(r'\d', texto):
            continue
        if texto.upper() == texto:                       # siglas e apelidos em maiúsculas (citações)
            continue
        if re.fullmatch(r"\w{1,2}\.?|\w+\.", palavras[-1]):  # termina em abreviatura cortada (D. Fr)
            continue
        if rotulo == 'PER' and len(palavras) < 2:
            continue
        if len(palavras) == 1:
            p = palavras[0].lower()
            if minus[p] >= 0.15 * max(maius[p], 1):      # palavra comum escrita com maiúscula
                continue
        if VIA.match(texto):
            rotulo = 'LOC'
            texto = VIAS.get(palavras[0], palavras[0]) + texto[len(palavras[0]):]
        k = chave(texto)
        if not k or k in conhecidos:
            continue
        c = cand[k]
        c['n'] += 1
        c['formas'][texto] += 1
        c['rotulo'][rotulo] += 1
        c['entradas'].setdefault(eid, frase)
    res = []
    for c in cand.values():
        if len(c['entradas']) < MIN_ENTRADAS:
            continue
        # preferir a forma por extenso mais usada (São Pedro em vez de S. Pedro)
        formas = sorted(c['formas'].items(), key=lambda f: (-('.' not in f[0]), -f[1]))
        res.append({'termo': formas[0][0], 'tipo': TIPO[c['rotulo'].most_common(1)[0][0]],
                    'ocorrencias': c['n'], 'entradas': c['entradas']})
    res.sort(key=lambda x: -len(x['entradas']))
    os.makedirs(os.path.dirname(SAIDA), exist_ok=True)
    json.dump(res, open(SAIDA, 'w'), ensure_ascii=False)
    por_tipo = collections.Counter(r['tipo'] for r in res)
    print(f'{len(res)} candidatos ({dict(por_tipo)}); {sum(len(r["entradas"]) for r in res)} ligações; gravado em {SAIDA}')
    for tipo in ('pessoa', 'lugar', 'instituicao'):
        amostra = [f'{r["termo"]} ({len(r["entradas"])})' for r in res if r['tipo'] == tipo][:25]
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
