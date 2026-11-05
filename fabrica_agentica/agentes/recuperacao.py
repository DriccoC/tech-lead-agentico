"""Fase 4 — Agente de recuperação sobre o índice FAISS existente do Manual de Engenharia.

Duas configurações, para diagnosticar e corrigir falhas de recuperação:
- SEM transformação: a ferramenta recebe a pergunta literal do usuário;
- COM transformação: a ferramenta aplica a estratégia híbrida multi-query + HyDE.

O agente deve responder citando norma e chunk_id, e declarar quando o manual não cobre.
"""

from __future__ import annotations

import json

from langchain_classic.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from fabrica_agentica.config import criar_llm
from fabrica_agentica.ferramentas import rag
from fabrica_agentica.ferramentas.transformacao_consulta import documento_hipotetico, variacoes

SISTEMA = (
    "Você é o agente de recuperação do Manual de Engenharia da NovaForja (empresa fictícia). Responda SOMENTE com "
    "base nos trechos devolvidos pela ferramenta, em português, citando a norma e o chunk_id. Se nenhum trecho "
    "responder à pergunta, diga claramente que o manual não cobre o assunto — não use conhecimento geral."
)


def _resultado(resultados: list[dict], consultas: list[str]) -> str:
    return json.dumps({"consultas_usadas": consultas, "resultados": resultados}, ensure_ascii=False)


@tool
def buscar_manual_literal(pergunta_do_usuario: str) -> str:
    """Busca no Manual de Engenharia usando exatamente a pergunta do usuário (copie-a sem alterar)."""
    return _resultado(rag.buscar(pergunta_do_usuario, k=3), [pergunta_do_usuario])


@tool
def buscar_manual_transformado(pergunta_do_usuario: str) -> str:
    """Busca no Manual de Engenharia aplicando transformação de consulta (multi-query em português formal +
    documento hipotético/HyDE). Passe a pergunta do usuário sem alterar."""
    consultas = [*variacoes(pergunta_do_usuario), documento_hipotetico(pergunta_do_usuario)]
    return _resultado(rag.buscar_varias(consultas, k=3), consultas)


def criar_agente_recuperacao(com_transformacao: bool) -> AgentExecutor:
    ferramenta = buscar_manual_transformado if com_transformacao else buscar_manual_literal
    prompt = ChatPromptTemplate.from_messages(
        [("system", SISTEMA), ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")]
    )
    agente = create_openai_tools_agent(criar_llm("agente"), [ferramenta], prompt)
    return AgentExecutor(agent=agente, tools=[ferramenta], max_iterations=3, return_intermediate_steps=True, handle_parsing_errors=True)


def fontes(resultado: dict) -> list[dict]:
    """Documentos-fonte efetivamente devolvidos ao agente (para o diagnóstico)."""
    saida = []
    for _, observacao in resultado.get("intermediate_steps", []):
        dados = json.loads(observacao)
        for r in dados["resultados"]:
            saida.append({"chunk_id": r["chunk_id"], "doc": r["doc_id"], "secao": r["secao"], "distancia": r["distancia_l2"],
                          "similaridade": r["similaridade"], "inicio": r["trecho"][:110].replace("\n", " ")})
    return saida
