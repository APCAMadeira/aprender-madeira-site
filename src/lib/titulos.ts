// Maiúsculas nos títulos (decisão de 21/11/2026).
// Os títulos antigos estão em minúsculas no Directus. Esta função só acrescenta maiúsculas,
// nunca as tira, por isso continua certa depois de os títulos serem corrigidos na base de dados.
// As mesmas regras servem para gerar a lista de correções a rever no Directus.

const PARTICULAS = new Set([
  'a', 'o', 'os', 'as', 'e', 'de', 'da', 'do', 'das', 'dos', 'd', 'em', 'no', 'na', 'nos', 'nas',
  'com', 'para', 'por', 'pela', 'pelo', 'à', 'ao', 'aos', 'às', 'y', 'del', 'la', 'las', 'los', 'el',
  'von', 'van', 'der', 'of', 'the', 'and',
]);
const ROMANOS = /^(i|ii|iii|iv|v|vi|vii|viii|ix|x|xi|xii|xiii|xiv|xv|xvi|xvii|xviii|xix|xx|xxi)$/i;
const NOMES_PROPRIOS = new Set(['biografia', 'lugar', 'instituicao', 'edificio']);

function maiuscula(p: string): string {
  return p.charAt(0).toLocaleUpperCase('pt-PT') + p.slice(1);
}

function cadaPalavra(titulo: string, siglasEntreParenteses: boolean): string {
  const partes = titulo.split(/(\s+|-|\(|\)|,|\/)/);
  let dentroParenteses = false;
  return partes
    .map((p, i) => {
      if (p === '(') dentroParenteses = true;
      if (p === ')') dentroParenteses = false;
      if (!p || /^[\s\-(),/]+$/.test(p)) return p;
      if (ROMANOS.test(p) && i > 0) return p.toLocaleUpperCase('pt-PT');
      if (siglasEntreParenteses && dentroParenteses && /^[a-zà-ú]{2,6}$/i.test(p) && partes.filter((x) => /\w/.test(x)).length > 1) {
        return p.toLocaleUpperCase('pt-PT');
      }
      if (i > 0 && PARTICULAS.has(p.toLocaleLowerCase('pt-PT'))) return p;
      return maiuscula(p);
    })
    .join('');
}

export function tituloApresentacao(titulo: string, tipo: string, traducao = false): string {
  if (!titulo) return titulo;
  if (traducao) return maiuscula(titulo);
  // Títulos descritivos (com dois pontos) não são nomes próprios: só a primeira letra.
  if (NOMES_PROPRIOS.has(tipo) && !titulo.includes(':')) return cadaPalavra(titulo, tipo !== 'biografia');
  return maiuscula(titulo);
}
