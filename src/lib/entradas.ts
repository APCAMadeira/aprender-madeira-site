// Funções de apoio às páginas de entrada.
import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import type { Autor, Entrada, Lingua } from './dados';
import { PREFIXO } from './textos';

// Endereço de uma entrada: o português mantém o endereço antigo /article/<slug>.
export function urlEntrada(e: Pick<Entrada, 'slug' | 'traducoes'>, l: Lingua): string {
  if (l === 'pt') return `/article/${e.slug}/`;
  const t = e.traducoes.find((x) => x.lingua === l);
  return `${PREFIXO[l]}/article/${t?.slug || e.slug}/`;
}

export function temTraducao(e: Entrada, l: Lingua): boolean {
  return l === 'pt' || e.traducoes.some((t) => t.lingua === l);
}

// Conteúdo na língua pedida (ou em português, se não houver tradução).
export function conteudo(e: Entrada, l: Lingua) {
  const t = l === 'pt' ? undefined : e.traducoes.find((x) => x.lingua === l);
  return {
    titulo: t?.titulo || e.titulo,
    corpo: t?.corpo || e.corpo,
    resumo: t?.resumo || e.resumo || '',
    traducao: t,
  };
}

// Nas versões traduzidas, as ligações internas apontam para a mesma língua quando existe tradução.
export function ajustarLigacoes(html: string, l: Lingua, comTraducao: Set<string>): string {
  if (l === 'pt') return html;
  return html.replace(/href="\/article\/([^"#?/]+)\/?"/g, (m, slug) =>
    comTraducao.has(slug) ? `href="${PREFIXO[l]}/article/${slug}/"` : m);
}

export function textoSimples(html: string): string {
  return html.replace(/<[^>]+>/g, ' ').replace(/&nbsp;/g, ' ').replace(/\s+/g, ' ').trim();
}

export function minutosLeitura(html: string): number {
  return Math.max(1, Math.round(textoSimples(html).split(' ').length / 200));
}

export function excerto(html: string, max = 160): string {
  const t = textoSimples(html);
  if (t.length <= max) return t;
  return t.slice(0, t.lastIndexOf(' ', max)) + '…';
}

// "Rui Carita" -> "CARITA, Rui" (ou o nome de citação registado no Directus).
export function nomeCitacao(a: Autor): string {
  if (a.nomeCitacao) return a.nomeCitacao;
  const partes = a.nome.trim().split(/\s+/);
  if (partes.length < 2) return a.nome.toLocaleUpperCase('pt-PT');
  const apelido = partes.pop() as string;
  return `${apelido.toLocaleUpperCase('pt-PT')}, ${partes.join(' ')}`;
}

// As referências antigas vêm num só bloco, separadas por ponto e vírgula antes de cada apelido.
export function separarReferencias(fontes: { referencia: string }[]): string[] {
  return fontes
    .flatMap((f) => f.referencia.split(/;\s+(?=[A-ZÁÉÍÓÚÂÊÔÃÕÇ][A-ZÁÉÍÓÚÂÊÔÃÕÇ'\- ]+,)/))
    .map((r) => r.replace(/<[^>]+>/g, '').trim().replace(/[;.]?$/, '.'))
    .filter((r) => r.length > 3);
}

export interface Citacao { fonte: string; lingua?: string; titulo: string; url: string }
export interface Citacoes { geradoEm?: string; paginasWikipedia: number; porEntrada: Record<string, Citacao[]> }

let cacheCitacoes: Promise<Citacoes> | null = null;
export function carregarCitacoes(): Promise<Citacoes> {
  if (!cacheCitacoes) {
    cacheCitacoes = (async () => {
      if (!existsSync('dados/citacoes.json')) return { paginasWikipedia: 0, porEntrada: {} };
      return JSON.parse(await readFile('dados/citacoes.json', 'utf-8')) as Citacoes;
    })();
  }
  return cacheCitacoes;
}
