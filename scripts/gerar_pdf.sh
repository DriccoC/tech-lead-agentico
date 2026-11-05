#!/bin/zsh
# Gera relatorio/adriano_carvalho_ai-agents_langchain-agents.pdf a partir de relatorio/relatorio.md
# Requer pandoc e Google Chrome.
set -e
cd "$(dirname "$0")/../relatorio"
pandoc relatorio.md -s --toc --toc-depth=2 -M toc-title="Sumário" -M lang=pt-BR -c estilo.css --resource-path=. -o relatorio.html
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --no-pdf-header-footer \
  --print-to-pdf="adriano_carvalho_ai-agents_langchain-agents.pdf" "file://$PWD/relatorio.html" 2>/dev/null
echo "PDF gerado: $PWD/adriano_carvalho_ai-agents_langchain-agents.pdf"
