// Camada de dados do site.
// Em produção lê o Directus (variáveis DIRECTUS_URL e DIRECTUS_TOKEN, só de leitura).
// Sem essas variáveis usa a amostra em dados/amostra.json, para desenvolvimento.
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';

export type Lingua = 'pt' | 'en' | 'es';

export interface Autor { nome: string; slug: string; nomeCitacao?: string }
export interface Imagem { id: string; largura?: number; altura?: number; legenda?: string; creditos?: string }
export interface Subtema { slug: string; nome: string; tema: string }
export interface Tema { slug: string; nome: string; total: number; subtemas: { slug: string; nome: string }[] }
export interface Fonte { referencia: string; url?: string }
export interface Ligacao { slug: string; titulo: string; tipo: string }
export interface Traducao {
  lingua: 'en' | 'es';
  titulo: string;
  slug: string;
  corpo: string;
  resumo?: string;
  estado: string;
  origem: string;
}
export interface Entrada {
  slug: string;
  titulo: string;
  tipo: string;
  resumo?: string;
  corpo: string;
  dataPublicacao?: string | null;
  dataAtualizacao?: string | null;
  autores: Autor[];
  categorias: Subtema[];
  imagens: Imagem[];
  fontes: Fonte[];
  relacionadas: Ligacao[];
  traducoes: Traducao[];
  doi?: string;
}
export interface FotoAbertura { id: string; legenda: string; alt: string }
export interface Acervo {
  origem: string;
  totais: { entradas: number; biografias: number; autores: number; traducoes: number };
  tipos: Record<string, number>;
  temas: Tema[];
  entradas: Entrada[];
  abertura: FotoAbertura[];
}

const DIRECTUS_URL = process.env.DIRECTUS_URL?.replace(/\/$/, '');
const DIRECTUS_TOKEN = process.env.DIRECTUS_TOKEN;
const MAPA_LINGUAS: Record<string, 'en' | 'es'> = { 'en-GB': 'en', 'en-US': 'en', en: 'en', 'es-ES': 'es', es: 'es' };

let cache: Promise<Acervo> | null = null;

export function carregarAcervo(): Promise<Acervo> {
  if (!cache) cache = DIRECTUS_URL && DIRECTUS_TOKEN ? doDirectus() : daAmostra();
  return cache;
}

async function lerJson<T>(caminho: string): Promise<T | null> {
  if (!existsSync(caminho)) return null;
  return JSON.parse(await readFile(caminho, 'utf-8')) as T;
}

async function daAmostra(): Promise<Acervo> {
  const a = await lerJson<Omit<Acervo, 'abertura'>>('dados/amostra.json');
  if (!a) throw new Error('Falta dados/amostra.json e não há ligação ao Directus.');
  const abertura = (await lerJson<FotoAbertura[]>('dados/abertura.json')) ?? [];
  const entradas = a.entradas.map(completarRelacionadas(a.entradas));
  return { ...a, entradas, abertura };
}

async function api<T>(caminho: string): Promise<T> {
  const r = await fetch(`${DIRECTUS_URL}${caminho}`, { headers: { Authorization: `Bearer ${DIRECTUS_TOKEN}` } });
  if (!r.ok) throw new Error(`Directus respondeu ${r.status} em ${caminho}`);
  return ((await r.json()) as { data: T }).data;
}

const CAMPOS = [
  'slug', 'titulo', 'tipo', 'resumo', 'corpo', 'data_publicacao', 'data_atualizacao', 'doi',
  'autores.papel', 'autores.ordem', 'autores.autores_id.nome', 'autores.autores_id.slug', 'autores.autores_id.nome_citacao',
  'categorias.categorias_id.slug', 'categorias.categorias_id.nome', 'categorias.categorias_id.pai.slug',
  'imagens.ordem', 'imagens.legenda', 'imagens.creditos',
  'imagens.directus_files_id.id', 'imagens.directus_files_id.width', 'imagens.directus_files_id.height',
  'fontes.referencia', 'fontes.url', 'fontes.ordem',
  'relacionadas.related_entradas_id.slug', 'relacionadas.related_entradas_id.titulo',
  'relacionadas.related_entradas_id.tipo', 'relacionadas.related_entradas_id.estado',
  'translations.languages_code', 'translations.titulo', 'translations.slug', 'translations.resumo',
  'translations.corpo', 'translations.estado_traducao', 'translations.origem_traducao',
].join(',');

async function doDirectus(): Promise<Acervo> {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const brutas = await api<any[]>(`/items/entradas?limit=-1&filter[estado][_eq]=publicado&fields=${CAMPOS}`);
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const cats = await api<any[]>('/items/categorias?limit=-1&sort=ordem&fields=slug,nome,ordem,pai.slug');

  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  const entradas: Entrada[] = brutas.map((e: any) => ({
    slug: e.slug,
    titulo: e.titulo,
    tipo: e.tipo,
    resumo: e.resumo ?? '',
    corpo: e.corpo ?? '',
    dataPublicacao: e.data_publicacao,
    dataAtualizacao: e.data_atualizacao,
    doi: e.doi ?? '',
    autores: (e.autores ?? [])
      .filter((a: any) => a.autores_id)
      .sort((a: any, b: any) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .map((a: any) => ({ nome: a.autores_id.nome, slug: a.autores_id.slug, nomeCitacao: a.autores_id.nome_citacao ?? undefined })),
    categorias: (e.categorias ?? [])
      .filter((c: any) => c.categorias_id?.pai?.slug)
      .map((c: any) => ({ slug: c.categorias_id.slug, nome: c.categorias_id.nome, tema: c.categorias_id.pai.slug })),
    imagens: (e.imagens ?? [])
      .filter((i: any) => i.directus_files_id)
      .sort((a: any, b: any) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .map((i: any) => ({
        id: i.directus_files_id.id, largura: i.directus_files_id.width, altura: i.directus_files_id.height,
        legenda: limparLegenda(i.legenda), creditos: i.creditos ?? '',
      })),
    fontes: (e.fontes ?? [])
      .sort((a: any, b: any) => (a.ordem ?? 0) - (b.ordem ?? 0))
      .map((f: any) => ({ referencia: f.referencia, url: f.url ?? '' })),
    relacionadas: (e.relacionadas ?? [])
      .map((r: any) => r.related_entradas_id)
      .filter((r: any) => r && r.estado === 'publicado')
      .map((r: any) => ({ slug: r.slug, titulo: r.titulo, tipo: r.tipo })),
    traducoes: (e.translations ?? [])
      .filter((t: any) => MAPA_LINGUAS[t.languages_code] && t.corpo)
      .map((t: any) => ({
        lingua: MAPA_LINGUAS[t.languages_code], titulo: t.titulo, slug: t.slug || e.slug,
        corpo: t.corpo, resumo: t.resumo ?? '', estado: t.estado_traducao ?? '', origem: t.origem_traducao ?? '',
      })),
  }));

  const temas: Tema[] = cats.filter((c: any) => !c.pai).map((t: any) => ({
    slug: t.slug, nome: t.nome, total: 0,
    subtemas: cats.filter((s: any) => s.pai?.slug === t.slug).map((s: any) => ({ slug: s.slug, nome: s.nome })),
  }));
  for (const t of temas) t.total = entradas.filter((e) => e.categorias.some((c) => c.tema === t.slug)).length;

  const tipos: Record<string, number> = {};
  for (const e of entradas) tipos[e.tipo] = (tipos[e.tipo] ?? 0) + 1;
  const autores = new Set(entradas.flatMap((e) => e.autores.map((a) => a.slug || a.nome)));

  return {
    origem: 'directus',
    totais: {
      entradas: entradas.length,
      biografias: tipos['biografia'] ?? 0,
      autores: autores.size,
      traducoes: entradas.reduce((n, e) => n + e.traducoes.length, 0),
    },
    tipos,
    temas,
    entradas: entradas.map(completarRelacionadas(entradas)),
    abertura: await fotosAbertura(),
  };
}

// Fotografias da abertura: a pasta "Abertura do site" no Directus; se não existir, dados/abertura.json.
async function fotosAbertura(): Promise<FotoAbertura[]> {
  try {
    const pastas = await api<{ id: string }[]>('/folders?filter[name][_eq]=Abertura%20do%20site&fields=id');
    if (pastas.length) {
      const ficheiros = await api<{ id: string; title?: string; description?: string }[]>(
        `/files?limit=-1&filter[folder][_eq]=${pastas[0].id}&filter[type][_starts_with]=image&fields=id,title,description`);
      if (ficheiros.length) {
        return ficheiros.map((f) => ({ id: f.id, legenda: f.title ?? '', alt: f.description || f.title || '' }));
      }
    }
  } catch {
    // sem pasta ou sem permissão: usa o ficheiro local
  }
  return (await lerJson<FotoAbertura[]>('dados/abertura.json')) ?? [];
}

function limparLegenda(l?: string | null): string {
  return (l ?? '').replace(/<[^>]+>/g, '').replace(/\s+/g, ' ').trim();
}

// Se uma entrada não tiver "relacionadas" no Directus, usa as ligações internas do próprio texto.
function completarRelacionadas(todas: Entrada[]) {
  const porSlug = new Map(todas.map((e) => [e.slug, e]));
  return (e: Entrada): Entrada => {
    if (e.relacionadas.length) return e;
    const vistos: Ligacao[] = [];
    for (const m of e.corpo.matchAll(/href="\/article\/([^"#?/]+)/g)) {
      const alvo = porSlug.get(m[1]);
      if (alvo && alvo.slug !== e.slug && !vistos.some((v) => v.slug === alvo.slug)) {
        vistos.push({ slug: alvo.slug, titulo: alvo.titulo, tipo: alvo.tipo });
      }
    }
    return { ...e, relacionadas: vistos.slice(0, 6) };
  };
}

// Larguras geradas para cada imagem (ver scripts/imagens.mjs).
export const LARGURAS = { cartao: 640, grande: 1600, abertura: 1920 } as const;

// Endereço de uma imagem.
// No servidor (IMAGENS_LOCAIS=1) as imagens são copiadas do Directus para o próprio site,
// por isso o Directus nunca fica aberto ao público. Em desenvolvimento usa o Directus diretamente.
export function urlImagem(id: string, largura: number = LARGURAS.grande): string {
  if (process.env.IMAGENS_LOCAIS === '1') return `/imagens/${id}-${largura}.webp`;
  const base = (process.env.ASSETS_URL || DIRECTUS_URL || 'https://cms.aprenderamadeira.net').replace(/\/$/, '');
  return `${base}/assets/${id}?width=${largura}&quality=78&format=webp&withoutEnlargement=true`;
}

// As imagens dentro dos textos apontam para o Directus; no servidor passam a apontar para a cópia local.
export function imagensDoTexto(html: string): string {
  if (process.env.IMAGENS_LOCAIS !== '1') return html;
  return html
    .replace(/https?:\/\/cms\.aprenderamadeira\.net\/assets\/([0-9a-f-]{36})[^"'\s]*/g, `/imagens/$1-${LARGURAS.grande}.webp`)
    .replace(/\s(srcset|sizes)="[^"]*"/g, '');
}
