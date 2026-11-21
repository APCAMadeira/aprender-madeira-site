// Conta os artigos da Wikipédia que ligam ao Aprender Madeira e grava dados/citacoes.json.
// Corre no servidor uma vez por semana, antes de reconstruir o site. Não precisa de chave nem tem custo.
// Uso: node scripts/citacoes.mjs
import { writeFile, mkdir } from 'node:fs/promises';

const WIKIS = ['pt', 'en', 'es'];
const CONSULTAS = ['aprenderamadeira.net', '*.aprenderamadeira.net'];
const PROTOCOLOS = ['https', 'http'];
const AGENTE = 'AprenderMadeira/1.0 (https://aprenderamadeira.net; info@apca-madeira.org)';

async function ligacoes(wiki, consulta, protocolo) {
  const todas = [];
  let continuar = {};
  for (let i = 0; i < 50; i++) {
    const p = new URLSearchParams({
      action: 'query', list: 'exturlusage', euquery: consulta, euprotocol: protocolo,
      eunamespace: '0', eulimit: '500', format: 'json', ...continuar,
    });
    const r = await fetch(`https://${wiki}.wikipedia.org/w/api.php?${p}`, { headers: { 'User-Agent': AGENTE } });
    if (!r.ok) throw new Error(`Wikipédia ${wiki} respondeu ${r.status}`);
    const dados = await r.json();
    todas.push(...(dados.query?.exturlusage ?? []));
    if (!dados.continue) break;
    continuar = dados.continue;
  }
  return todas;
}

// /article/<slug> (formato atual) ou /<slug>/ (formato antigo do site)
function slugDe(url) {
  let caminho;
  try { caminho = decodeURIComponent(new URL(url).pathname); } catch { return null; }
  const m = caminho.match(/^\/article\/([^/]+)\/?$/) || caminho.match(/^\/([a-z0-9-]+)\/?$/);
  return m ? m[1].toLowerCase() : null;
}

const porEntrada = {};
const paginas = new Set();
for (const wiki of WIKIS) {
  for (const consulta of CONSULTAS) {
    for (const protocolo of PROTOCOLOS) {
      for (const l of await ligacoes(wiki, consulta, protocolo)) {
        paginas.add(`${wiki}:${l.title}`);
        const slug = slugDe(l.url);
        if (!slug) continue;
        const lista = (porEntrada[slug] ??= []);
        if (!lista.some((c) => c.lingua === wiki && c.titulo === l.title)) {
          lista.push({
            fonte: 'wikipedia', lingua: wiki, titulo: l.title,
            url: `https://${wiki}.wikipedia.org/wiki/${encodeURIComponent(l.title.replace(/ /g, '_'))}`,
          });
        }
      }
    }
  }
}

await mkdir('dados', { recursive: true });
await writeFile('dados/citacoes.json', JSON.stringify({
  geradoEm: new Date().toISOString(), paginasWikipedia: paginas.size, porEntrada,
}, null, 1));
console.log(`${paginas.size} artigos da Wikipédia; ${Object.keys(porEntrada).length} entradas citadas.`);
