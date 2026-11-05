"""Fase 2 — Chains sequenciais, paralelas e roteamento dinâmico (RouterChain)."""

from __future__ import annotations

import json

from langchain_classic.chains.router import MultiPromptChain
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

from fabrica_agentica.config import criar_llm
from fabrica_agentica.ferramentas import catalogo, rag
from fabrica_agentica.prompts import PROMPT_RESUMO


# ------------------------------------------------------------------ sequencial
def chain_sequencial():
    """Demanda -> resumo -> histórias -> riscos. Cada etapa recebe a saída das anteriores."""
    llm = criar_llm("auxiliar")
    texto = StrOutputParser()
    prompt_historias = ChatPromptTemplate.from_template(
        "Com base no resumo abaixo, escreva de 2 a 4 histórias de usuário no formato 'Como <papel>, quero <ação>, "
        "para <benefício>', uma por linha, em português.\n\nRESUMO: {resumo}"
    )
    prompt_riscos = ChatPromptTemplate.from_template(
        "Liste em até 3 tópicos curtos os riscos técnicos de entregar estas histórias, em português.\n\nHISTÓRIAS:\n{historias}"
    )
    return (
        RunnablePassthrough.assign(resumo=PROMPT_RESUMO | llm | texto)
        | RunnablePassthrough.assign(historias=prompt_historias | llm | texto)
        | RunnablePassthrough.assign(riscos=prompt_riscos | llm | texto)
    )


# ------------------------------------------------------------------ paralela
def _normas(entrada: dict) -> list[dict]:
    return [{"doc": r["doc_id"], "secao": r["secao"], "chunk": r["chunk_id"], "similaridade": r["similaridade"]}
            for r in rag.buscar(entrada["consulta_norma"], k=3)]


def _biblioteca(entrada: dict) -> dict:
    pypi = json.loads(catalogo.consultar_pypi.invoke({"pacote": entrada["pacote"]}))
    versao = pypi.get("versao_mais_recente", "0")
    osv = json.loads(catalogo.consultar_vulnerabilidades.invoke({"pacote": entrada["pacote"], "versao": versao}))
    return {"pacote": entrada["pacote"], "versao_mais_recente": versao, "vulnerabilidades": osv.get("total"), "maior_cvss": osv.get("maior_cvss")}


def _capacidade(entrada: dict) -> dict:
    cap = json.loads(catalogo.calcular_capacidade_sprint.invoke({"projeto": entrada["projeto"]}))
    return {k: cap.get(k) for k in ("sprint", "dias_uteis", "capacidade_liquida", "pontos_comprometidos", "saldo_disponivel")}


def chain_paralela():
    """Três checagens independentes ao mesmo tempo (normas || biblioteca || capacidade) e uma síntese."""
    checagens = RunnableParallel(
        normas=RunnableLambda(_normas),
        biblioteca=RunnableLambda(_biblioteca),
        capacidade=RunnableLambda(_capacidade),
        demanda=lambda x: x["demanda"],
    )
    sintese = ChatPromptTemplate.from_template(
        "Você é um líder técnico. Em até 5 linhas, em português, diga se a demanda é viável na próxima sprint, citando os "
        "números exatamente como aparecem nas checagens (não recalcule).\n\nDEMANDA: {demanda}\nNORMAS: {normas}\n"
        "BIBLIOTECA: {biblioteca}\nCAPACIDADE: {capacidade}"
    ) | criar_llm("auxiliar") | StrOutputParser()
    return checagens | RunnablePassthrough.assign(sintese=sintese)


# ------------------------------------------------------------------ roteamento (RouterChain)
ROTAS = [
    {
        "name": "planejamento",
        "description": "Bom para planejar demandas, histórias, estimativas, capacidade de sprint e backlog",
        "prompt_template": (
            "Você é um líder técnico especialista em planejamento ágil (MAN-06: Fibonacci, histórias de até 8 pontos, "
            "critérios Gherkin, reserva de 20% da capacidade). Responda em português, de forma objetiva.\n\n{input}"
        ),
    },
    {
        "name": "consulta_tecnica",
        "description": "Bom para dúvidas sobre normas internas, padrões de código, versionamento, implantação e Definição de Pronto",
        "prompt_template": (
            "Você é um arquiteto que conhece o Manual de Engenharia (DoD, padrões de código, trunk-based, janela de "
            "congelamento). Responda em português; se não tiver certeza da regra, diga que é preciso consultar o manual.\n\n{input}"
        ),
    },
    {
        "name": "seguranca",
        "description": "Bom para perguntas sobre bibliotecas, dependências, vulnerabilidades, CVE, CVSS e autenticação",
        "prompt_template": (
            "Você é um especialista em segurança de aplicações (MAN-04: CVSS >= 7,0 bloqueia adoção; MAN-05: OIDC com "
            "PKCE). Responda em português e recomende sempre checar a base OSV.\n\n{input}"
        ),
    },
]


def criar_router_chain(verbose: bool = False) -> MultiPromptChain:
    """RouterChain clássico: um LLMRouterChain escolhe a rota e o MultiPromptChain executa o prompt especialista."""
    return MultiPromptChain.from_prompts(llm=criar_llm("auxiliar"), prompt_infos=ROTAS, verbose=verbose)
