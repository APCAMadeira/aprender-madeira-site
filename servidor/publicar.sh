#!/bin/bash
# Gera o site a partir do Directus e publica-o na pasta do site.
# Uso (no servidor, como root):  bash servidor/publicar.sh [--semanal]
#   --semanal  também atualiza as citações da Wikipédia (corre uma vez por semana)
# Variáveis opcionais: DESTINO (pasta publicada), ENV_FILE (ficheiro com as chaves).
set -euo pipefail

SITE=/opt/aprendermadeira/site
ENV_FILE=${ENV_FILE:-/opt/aprendermadeira/env/site.env}
DESTINO=${DESTINO:-/home/giramo6/aprendermadeira2026/teste}
PERSISTENTE=/opt/aprendermadeira/site-dados   # imagens copiadas e citações (fora do Git)
REGISTO=/var/log/aprendermadeira-site.log

cd "$SITE"
git pull -q --ff-only
mkdir -p "$PERSISTENTE/imagens"

PASSOS="npm ci --no-audit --no-fund --loglevel=error"
if [ "${1:-}" = "--semanal" ]; then
  PASSOS="$PASSOS && node scripts/citacoes.mjs"
fi
PASSOS="$PASSOS && node scripts/imagens.mjs && npx astro build"

docker run --rm --network host --env-file "$ENV_FILE" \
  -v "$SITE":/app -v "$PERSISTENTE":/persistente -w /app node:22-alpine sh -c "$PASSOS"

# Páginas do site (sem tocar na proteção do site de teste) e imagens à parte
rsync -a --delete --exclude '.htaccess' --exclude '.htpasswd' --exclude '.well-known' --exclude '.user.ini' \
  --exclude 'robots.txt' --exclude 'php.ini' --exclude 'cgi-bin/' --exclude 'imagens/' \
  "$SITE/dist/" "$DESTINO/"
rsync -a "$PERSISTENTE/imagens/" "$DESTINO/imagens/"
chown -R giramo6:giramo6 "$DESTINO"

echo "$(date '+%F %T') site publicado em $DESTINO ($(git rev-parse --short HEAD))" | tee -a "$REGISTO"
