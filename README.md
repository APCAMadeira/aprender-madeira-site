# Aprender Madeira — site público

Site público do [Aprender Madeira](https://aprenderamadeira.net), projeto da
[APCA — Agência de Promoção da Cultura Atlântica](https://www.apca-madeira.org).

O site é estático: é gerado a partir do Directus (o gestor de conteúdos) e servido como ficheiros HTML.
Direção visual B («Atlântico»), escolhida a 21/11/2026.

## Como funciona

- **Conteúdo:** vem do Directus (`DIRECTUS_URL` e `DIRECTUS_TOKEN`, token só de leitura).
  Sem essas variáveis, o site usa a amostra em `dados/amostra.json` (30 entradas reais), para desenvolvimento.
- **Endereços:** as entradas em português mantêm o endereço antigo `/article/<slug>`;
  as traduções ficam em `/en/article/<slug>` e `/es/article/<slug>`.
- **Números da página inicial:** calculados a cada construção do site, por isso estão sempre atualizados.
- **Histórias do acervo e Pessoas:** escolhidas ao acaso, com a semana do ano como semente,
  por isso mudam todas as semanas e ficam iguais durante a semana.
- **Fotografias da abertura:** pasta «Abertura do site» no Directus (ou `dados/abertura.json`);
  rodam por ordem aleatória no browser, com botão de pausa.
- **Citações:** `scripts/citacoes.mjs` conta os artigos da Wikipédia (pt, en, es) que ligam ao site
  e grava `dados/citacoes.json`. Corre uma vez por semana no servidor.
- **Imagens:** no servidor (`IMAGENS_LOCAIS=1`), `scripts/imagens.mjs` copia do Directus para `public/imagens/`
  as imagens usadas, já em WebP e nos tamanhos certos. O Directus não precisa de ficar aberto ao público.
- **Pesquisa:** Meilisearch quando `PUBLIC_MEILI_URL` e `PUBLIC_MEILI_CHAVE` estão definidos;
  caso contrário, pesquisa simples no índice `/indice.json`.

## Comandos

```bash
npm ci              # instalar dependências
npm run dev         # site em desenvolvimento, em http://localhost:4321
npm run build       # gerar o site em dist/
npm run construir   # no servidor: copiar imagens do Directus e gerar o site
npm run citacoes    # atualizar dados/citacoes.json (precisa de acesso à Wikipédia)
```

Requer Node.js 22.12 ou mais recente. No servidor, a construção corre num contentor Docker `node:22`.

## Variáveis

Ver `.env.example`. O ficheiro `.env` com valores reais fica só no servidor e nunca vai para o GitHub.

## Estrutura

```
src/lib/dados.ts         leitura do Directus ou da amostra
src/lib/entradas.ts      endereços, citação, referências, tempo de leitura
src/lib/titulos.ts       maiúsculas nos títulos (até serem corrigidos no Directus)
src/lib/semana.ts        escolhas semanais ao acaso
src/lib/textos.ts        textos da interface em PT, EN e ES
src/components/          cabeçalho, rodapé, abertura, página inicial, página de entrada, pesquisa
src/pages/               endereços do site
scripts/citacoes.mjs     contagem semanal de citações na Wikipédia
dados/                   amostra, fotografias da abertura e citações
```
