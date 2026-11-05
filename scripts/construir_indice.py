"""Constrói o índice FAISS do Manual de Engenharia (executar UMA vez).

O enunciado pede um agente de recuperação sobre um índice FAISS *já existente*, sem
reconstruir o pipeline de indexação (coberto em outro bloco do curso). Este script
representa esse pipeline "de outro bloco": gera dados/indice_faiss/ e o agente apenas
carrega o índice pronto (ver fabrica_agentica/ferramentas/rag.py).

Uso:  python scripts/construir_indice.py
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_community.vectorstores import FAISS  # noqa: E402
from langchain_core.documents import Document  # noqa: E402
from langchain_text_splitters import RecursiveCharacterTextSplitter  # noqa: E402

from fabrica_agentica.config import CAMINHO_INDICE, CAMINHO_MANUAL, criar_embeddings  # noqa: E402

TAMANHO_CHUNK = 600
SOBREPOSICAO = 100


def carregar_documentos() -> list[Document]:
    """Lê cada norma e quebra por seção (##), guardando os metadados de origem."""
    documentos: list[Document] = []
    for arquivo in sorted(CAMINHO_MANUAL.glob("MAN-*.md")):
        texto = arquivo.read_text(encoding="utf-8")
        titulo = texto.splitlines()[0].lstrip("# ").strip()
        doc_id = titulo.split("—")[0].strip()
        for bloco in re.split(r"\n(?=## )", texto):
            linhas = bloco.strip().splitlines()
            secao = linhas[0].lstrip("# ").strip() if linhas else ""
            documentos.append(
                Document(
                    page_content=bloco.strip(),
                    metadata={"doc_id": doc_id, "titulo": titulo, "secao": secao, "arquivo": arquivo.name},
                )
            )
    return documentos


def construir() -> int:
    divisor = RecursiveCharacterTextSplitter(
        chunk_size=TAMANHO_CHUNK,
        chunk_overlap=SOBREPOSICAO,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = divisor.split_documents(carregar_documentos())
    for i, chunk in enumerate(chunks):
        chunk.metadata["chunk_id"] = f"CHK_{i:03d}"

    indice = FAISS.from_documents(chunks, criar_embeddings())
    CAMINHO_INDICE.mkdir(parents=True, exist_ok=True)
    indice.save_local(str(CAMINHO_INDICE))

    catalogo = [{"chunk_id": c.metadata["chunk_id"], **c.metadata, "inicio": c.page_content[:90]} for c in chunks]
    (CAMINHO_INDICE / "catalogo.json").write_text(json.dumps(catalogo, ensure_ascii=False, indent=1), encoding="utf-8")
    return len(chunks)


if __name__ == "__main__":
    print(f"Índice FAISS salvo em {CAMINHO_INDICE} com {construir()} chunks.")
