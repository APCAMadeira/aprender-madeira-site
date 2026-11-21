// Copia do Directus para public/imagens/ as imagens que o site usa, já redimensionadas em WebP.
// Assim o Directus nunca precisa de ficar aberto ao público.
// Só descarrega o que ainda não existe, por isso as construções seguintes são rápidas.
// Uso (no servidor, com DIRECTUS_URL e DIRECTUS_TOKEN): node scripts/imagens.mjs
import { mkdir, readFile, stat, writeFile } from 'node:fs/promises';

const URL_D = process.env.DIRECTUS_URL?.replace(/\/$/, '');
const TOKEN = process.env.DIRECTUS_TOKEN;
if (!URL_D || !TOKEN) {
  console.error('Faltam DIRECTUS_URL e DIRECTUS_TOKEN.');
  process.exit(1);
}
const PASTA = process.env.IMAGENS_DIR || 'public/imagens';
const CARTAO = 640, GRANDE = 1600, ABERTURA = 1920;

async function api(caminho) {
  const r = await fetch(`${URL_D}${caminho}`, { headers: { Authorization: `Bearer ${TOKEN}` } });
  if (!r.ok) throw new Error(`Directus respondeu ${r.status} em ${caminho}`);
  return (await r.json()).data;
}

const pedidos = new Map(); // "id-largura" -> [id, largura]
const pedir = (id, largura) => pedidos.set(`${id}-${largura}`, [id, largura]);

const entradas = await api('/items/entradas?limit=-1&filter[estado][_eq]=publicado&fields=corpo,imagens.directus_files_id,translations.corpo');
for (const e of entradas) {
  for (const i of e.imagens ?? []) {
    if (i.directus_files_id) { pedir(i.directus_files_id, CARTAO); pedir(i.directus_files_id, GRANDE); }
  }
  const textos = [e.corpo ?? '', ...(e.translations ?? []).map((t) => t.corpo ?? '')].join(' ');
  for (const m of textos.matchAll(/cms\.aprenderamadeira\.net\/assets\/([0-9a-f-]{36})/g)) pedir(m[1], GRANDE);
}

let abertura = [];
try {
  const pastas = await api('/folders?filter[name][_eq]=Abertura%20do%20site&fields=id');
  if (pastas.length) abertura = (await api(`/files?limit=-1&filter[folder][_eq]=${pastas[0].id}&fields=id`)).map((f) => f.id);
} catch { /* sem pasta */ }
if (!abertura.length) {
  try { abertura = JSON.parse(await readFile('dados/abertura.json', 'utf-8')).map((f) => f.id); } catch { /* sem ficheiro */ }
}
for (const id of abertura) pedir(id, ABERTURA);

await mkdir(PASTA, { recursive: true });
let novas = 0, falhas = 0;
const lista = [...pedidos.values()];
const existe = async (f) => { try { await stat(f); return true; } catch { return false; } };
for (let i = 0; i < lista.length; i += 6) {
  await Promise.all(lista.slice(i, i + 6).map(async ([id, largura]) => {
    const destino = `${PASTA}/${id}-${largura}.webp`;
    if (await existe(destino)) return;
    const r = await fetch(`${URL_D}/assets/${id}?width=${largura}&quality=78&format=webp&withoutEnlargement=true`,
      { headers: { Authorization: `Bearer ${TOKEN}` } });
    if (!r.ok) { falhas++; console.warn(`Falhou ${id} (${r.status})`); return; }
    await writeFile(destino, Buffer.from(await r.arrayBuffer()));
    novas++;
  }));
}
console.log(`${pedidos.size} imagens pedidas; ${novas} novas; ${falhas} falhas.`);
