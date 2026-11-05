"""Fase 1 — Chain MVP: demanda em linguagem natural -> triagem técnica em JSON.

A mesma chain é implementada de duas formas:
- DECLARATIVA (LCEL):   prompt | modelo | parser
- IMPERATIVA (@chain):  função Python com controle total (aqui: uma nova tentativa
                        quando o modelo devolve um JSON inválido)

Decisão do projeto: LCEL é o padrão de composição (batch/stream/async nativos, tracing
por etapa no LangSmith, composição com outras chains); @chain é usado apenas onde há
lógica condicional que não cabe num pipe (como a nova tentativa abaixo).
"""

from __future__ import annotations

from langchain_core.exceptions import OutputParserException
from langchain_core.messages import HumanMessage
from langchain_core.output_parsers import PydanticOutputParser, StrOutputParser
from langchain_core.runnables import chain

from fabrica_agentica.config import criar_llm, texto_de
from fabrica_agentica.esquemas import AnaliseDemanda
from fabrica_agentica.prompts import PROMPT_ANALISE, PROMPT_RESUMO

parser_analise = PydanticOutputParser(pydantic_object=AnaliseDemanda)
prompt_analise = PROMPT_ANALISE.partial(instrucoes_formato=parser_analise.get_format_instructions())


def chain_resumo():
    """PromptTemplate (texto simples) -> modelo -> texto."""
    return PROMPT_RESUMO | criar_llm("auxiliar") | StrOutputParser()


def chain_analise_lcel():
    """Composição declarativa: prompt | modelo | parser JSON."""
    return prompt_analise | criar_llm("agente") | parser_analise


@chain
def analisar_demanda_imperativa(demanda: str) -> AnaliseDemanda:
    """Composição imperativa: mesma lógica, com uma nova tentativa se o JSON vier inválido."""
    llm = criar_llm("agente")
    mensagens = prompt_analise.format_messages(demanda=demanda)
    resposta = llm.invoke(mensagens)
    try:
        return parser_analise.parse(texto_de(resposta))
    except OutputParserException as erro:
        correcao = HumanMessage(
            content=f"Sua resposta não é um JSON válido para o esquema ({erro}). Responda novamente apenas com o JSON."
        )
        resposta = llm.invoke([*mensagens, resposta, correcao])
        return parser_analise.parse(texto_de(resposta))
