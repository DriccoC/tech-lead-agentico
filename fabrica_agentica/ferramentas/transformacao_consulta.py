"""Transformação de consulta para corrigir descompasso de vocabulário no RAG.

O manual usa linguagem normativa ("ramo principal protegido", "solicitação de
incorporação", "janela de congelamento"); o time pergunta em jargão ("subir direto na
main", "meu PR", "deploy na sexta"). Três técnicas, comparadas no notebook da Fase 4:

- REESCRITA: o LLM reescreve a pergunta como consulta técnica formal.
- MULTI-QUERY: o LLM gera variações; junta-se o melhor resultado de cada uma.
- HyDE (Hypothetical Document Embeddings): o LLM escreve um trecho HIPOTÉTICO de norma que
  responderia à pergunta; busca-se pelo embedding desse trecho.

Também há o conjunto de casos difíceis com gabarito (chunk correto) e as métricas.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel, Field

from fabrica_agentica.config import criar_llm, modo_demo, texto_de
from fabrica_agentica.ferramentas import rag

INSTRUCAO_FORMAL = (
    "Reescreva a pergunta de um desenvolvedor como uma consulta de busca para um manual de normas técnicas de "
    "engenharia de software escrito em português formal. Troque gírias e anglicismos (PR, deploy, lib, branch, main, "
    "master, commitar, subir) pelos termos técnicos formais equivalentes em português, mantendo também o termo "
    "original entre parênteses. Não responda à pergunta. Devolva só a consulta, numa linha."
)


class Variacoes(BaseModel):
    consultas: list[str] = Field(description="3 formulações diferentes da pergunta, em português formal de normas técnicas")


def reescrever(pergunta: str) -> str:
    if modo_demo():
        from fabrica_agentica.demo.roteiro import reescrever_consulta

        return reescrever_consulta(pergunta)
    return texto_de(criar_llm("auxiliar").invoke(f"{INSTRUCAO_FORMAL}\n\nPERGUNTA: {pergunta}")).strip()


def variacoes(pergunta: str) -> list[str]:
    if modo_demo():
        return [pergunta, reescrever(pergunta)]
    gerador = criar_llm("auxiliar").with_structured_output(Variacoes, method="json_schema")
    resultado: Variacoes = gerador.invoke(
        f"{INSTRUCAO_FORMAL.replace('uma consulta de busca', 'TRÊS consultas de busca diferentes')}\n\nPERGUNTA: {pergunta}"
    )
    return [pergunta, *resultado.consultas[:3]]


def documento_hipotetico(pergunta: str) -> str:
    if modo_demo():
        return f"Norma interna. {reescrever(pergunta)}. Fica estabelecido que a regra aplicável deve ser seguida."
    return texto_de(
        criar_llm("auxiliar").invoke(
            "Escreva um parágrafo curto (3 frases) no estilo de uma norma corporativa de engenharia de software, em "
            "português formal, que responderia à pergunta abaixo. Pode inventar os detalhes: o texto serve apenas "
            f"para busca semântica.\n\nPERGUNTA: {pergunta}"
        )
    )


# ------------------------------------------------------------------ estratégias de busca
def busca_direta(pergunta: str, k: int = 4) -> list[dict]:
    return rag.buscar(pergunta, k=k)


def busca_reescrita(pergunta: str, k: int = 4) -> list[dict]:
    return rag.buscar(reescrever(pergunta), k=k)


def busca_multi_query(pergunta: str, k: int = 4) -> list[dict]:
    return rag.buscar_varias(variacoes(pergunta), k=k)


def busca_hyde(pergunta: str, k: int = 4) -> list[dict]:
    return rag.buscar(documento_hipotetico(pergunta), k=k)


ESTRATEGIAS: dict[str, Callable[[str], list[dict]]] = {
    "direta (sem transformação)": busca_direta,
    "reescrita": busca_reescrita,
    "multi-query": busca_multi_query,
    "HyDE": busca_hyde,
}

# ------------------------------------------------------------------ casos difíceis com gabarito
CASOS_DIFICEIS = [
    {"pergunta": "quem precisa revisar meu PR?", "gabarito": ["CHK_003"]},
    {"pergunta": "posso commitar direto no master?", "gabarito": ["CHK_012"]},
    {"pergunta": "posso subir direto na main na sexta?", "gabarito": ["CHK_012", "CHK_014"]},
    {"pergunta": "qual a cobertura mínima de testes?", "gabarito": ["CHK_002"]},
    {"pergunta": "posso usar uma lib com CVE alta?", "gabarito": ["CHK_019"]},
    {"pergunta": "dá pra fazer deploy sexta à tarde?", "gabarito": ["CHK_014"]},
    {"pergunta": "o cliente errou a senha várias vezes, o que acontece?", "gabarito": ["CHK_027"]},
    {"pergunta": "uma história de 13 pontos pode entrar na sprint?", "gabarito": ["CHK_032"]},
    {"pergunta": "o login com Google tem que passar pelo Keycloak?", "gabarito": ["CHK_039"]},
    {"pergunta": "quanto tempo pode durar um branch?", "gabarito": ["CHK_013"]},
    {"pergunta": "precisa de dois fatores pra pagar fatura?", "gabarito": ["CHK_028"]},
    {"pergunta": "quais linters a gente usa em Python?", "gabarito": ["CHK_007"]},
    {"pergunta": "toda lib nova tem que ir pro SBOM?", "gabarito": ["CHK_010"]},
    {"pergunta": "posso usar o fluxo implícito do OAuth no front?", "gabarito": ["CHK_024"]},
]


def posicao_acerto(resultados: list[dict], gabarito: list[str]) -> int | None:
    for i, r in enumerate(resultados, 1):
        if r["chunk_id"] in gabarito:
            return i
    return None


def avaliar(estrategia: Callable[[str], list[dict]], casos: list[dict] = CASOS_DIFICEIS, k: int = 4) -> dict:
    linhas = []
    for caso in casos:
        resultados = estrategia(caso["pergunta"], k=k)
        pos = posicao_acerto(resultados, caso["gabarito"])
        linhas.append({
            "pergunta": caso["pergunta"],
            "posicao": pos,
            "top1": f"{resultados[0]['chunk_id']} {resultados[0]['doc_id']} {resultados[0]['secao'][:28]}" if resultados else "-",
            "dist_top1": resultados[0]["distancia_l2"] if resultados else None,
        })
    n = len(linhas)
    return {
        "hit@1": round(sum(1 for l in linhas if l["posicao"] == 1) / n, 3),
        "hit@3": round(sum(1 for l in linhas if l["posicao"] and l["posicao"] <= 3) / n, 3),
        "mrr@4": round(sum(1 / l["posicao"] for l in linhas if l["posicao"]) / n, 3),
        "linhas": linhas,
    }


def busca_multi_query_hyde(pergunta: str, k: int = 4) -> list[dict]:
    """Híbrida: variações formais (multi-query) + documento hipotético (HyDE), juntando os melhores trechos."""
    return rag.buscar_varias([*variacoes(pergunta), documento_hipotetico(pergunta)], k=k)


ESTRATEGIAS["multi-query + HyDE"] = busca_multi_query_hyde
