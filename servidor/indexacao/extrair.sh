#!/bin/bash
# Corre o extrator de nomes num contentor Python com spaCy (português).
# Uso (no servidor, como root):  bash servidor/indexacao/extrair.sh [--aplicar]
set -euo pipefail
SITE=/opt/aprendermadeira/site
SAIDA=/opt/aprendermadeira/indexacao
mkdir -p "$SAIDA" "$SAIDA/pip"
docker run --rm --network host \
  -v "$SITE/servidor/indexacao":/app:ro \
  -v /opt/aprendermadeira/env/operador.token:/env/operador.token:ro \
  -v "$SAIDA":/out -v "$SAIDA/pip":/root/.cache/pip \
  python:3.12-slim sh -c "pip install -q --root-user-action=ignore spacy==3.8.* && python -m spacy download pt_core_news_lg -q > /dev/null && python /app/extrator_nomes.py $*"
