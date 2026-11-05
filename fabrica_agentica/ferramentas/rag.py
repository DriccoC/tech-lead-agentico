"""Agente de recuperação sobre o índice FAISS EXISTENTE do Manual de Engenharia.

O índice é construído uma única vez por scripts/construir_indice.py (o "pipeline de
outro bloco"); aqui ele apenas é carregado. A desserialização exige
`allow_dangerous_deserialization=True` porque o FAISS salva metadados com pickle: isso é
seguro apenas porque o arquivo foi gerado por nós, nunca para índices de terceiros.

Diagnóstico "open-box": cada resultado traz a distância L2 (ao quadrado) entre vetores
normalizados — 0 = idêntico, 2 = ortogonal, 4 = oposto. Faixas calibradas
empiricamente com o modelo de embeddings deste projeto (ver notebook da Fase 4).
"""

from __future__ import annotations

from functools import lru_cache

from fabrica_agentica.config import CAMINHO_INDICE, criar_embeddings

FAIXA_ALTA = 0.80
FAIXA_MODERADA = 1.10


@lru_cache(maxsize=1)
def carregar_indice():
    from langchain_community.vectorstores import FAISS

    if not (CAMINHO_INDICE / "index.faiss").exists():
        raise FileNotFoundError("Índice não encontrado. Rode: python scripts/construir_indice.py")
    return FAISS.load_local(str(CAMINHO_INDICE), criar_embeddings(), allow_dangerous_deserialization=True)


def classificar_distancia(distancia: float) -> str:
    if distancia < FAIXA_ALTA:
        return "alta"
    if distancia <= FAIXA_MODERADA:
        return "moderada"
    return "baixa"


def buscar(consulta: str, k: int = 4, documento: str | None = None) -> list[dict]:
    """Busca por similaridade com diagnóstico de cada trecho recuperado."""
    filtro = {"doc_id": documento} if documento else None
    resultados = carregar_indice().similarity_search_with_score(consulta, k=k, filter=filtro, fetch_k=40)
    saida = []
    for doc, distancia in resultados:
        saida.append(
            {
                "chunk_id": doc.metadata.get("chunk_id"),
                "doc_id": doc.metadata.get("doc_id"),
                "secao": doc.metadata.get("secao"),
                "distancia_l2": round(float(distancia), 3),
                "similaridade": classificar_distancia(float(distancia)),
                "trecho": doc.page_content,
            }
        )
    return saida


def buscar_varias(consultas: list[str], k: int = 4, documento: str | None = None) -> list[dict]:
    """Multi-query: junta os resultados de várias consultas, mantendo a menor distância."""
    melhores: dict[str, dict] = {}
    for consulta in consultas:
        for r in buscar(consulta, k=k, documento=documento):
            atual = melhores.get(r["chunk_id"])
            if atual is None or r["distancia_l2"] < atual["distancia_l2"]:
                melhores[r["chunk_id"]] = {**r, "consulta_origem": consulta}
    return sorted(melhores.values(), key=lambda r: r["distancia_l2"])[:k]
