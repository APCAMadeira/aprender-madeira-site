// Índice leve para a pesquisa no browser enquanto o Meilisearch não estiver ligado.
import { carregarAcervo } from '../lib/dados';
import { excerto } from '../lib/entradas';
import { tituloApresentacao } from '../lib/titulos';

export async function GET() {
  const acervo = await carregarAcervo();
  const itens = acervo.entradas.map((e) => ({
    s: e.slug,
    t: tituloApresentacao(e.titulo, e.tipo),
    k: e.tipo,
    a: e.autores.map((a) => a.nome).join(', '),
    r: excerto(e.resumo || e.corpo, 140),
    l: e.traducoes.map((t) => t.lingua),
  }));
  return new Response(JSON.stringify(itens), { headers: { 'Content-Type': 'application/json; charset=utf-8' } });
}
