"""Fase 4 — Padrão text-to-query explícito: pergunta -> SQL -> execução -> resposta.

O agente também faz isso sozinho com a ferramenta `consultar_backlog_sql`; esta chain
deixa as etapas visíveis e adiciona AUTOCORREÇÃO: se o SQL falhar (erro de sintaxe ou
coluna inexistente), o erro volta ao LLM, que gera uma nova versão (até 2 tentativas).
"""

from __future__ import annotations

from pydantic import BaseModel, Field

from fabrica_agentica.config import criar_llm, texto_de
from fabrica_agentica.ferramentas import sql


class ConsultaSQL(BaseModel):
    raciocinio: str = Field(description="Em uma frase: quais tabelas e junções respondem à pergunta")
    sql: str = Field(description="Uma única consulta SELECT em SQLite")


PROMPT_SQL = (
    "Traduza a pergunta para UMA consulta SQL SQLite de leitura (SELECT), usando somente este esquema:\n"
    f"{sql.DICIONARIO_DADOS}\n\nSe a pergunta pedir alteração de dados, gere mesmo assim a consulta pedida: "
    "o guardrail decide se ela roda.\n"
)


def pergunta_para_sql(pergunta: str, tentativas: int = 2) -> dict:
    gerador = criar_llm("auxiliar").with_structured_output(ConsultaSQL, method="json_schema")
    historico: list[dict] = []
    prompt = f"{PROMPT_SQL}\nPERGUNTA: {pergunta}"
    for tentativa in range(1, tentativas + 1):
        consulta: ConsultaSQL = gerador.invoke(prompt)
        resultado = sql.executar_consulta(consulta.sql)
        historico.append({"tentativa": tentativa, "sql": consulta.sql, "ok": resultado["ok"], "erro": resultado.get("erro")})
        if resultado["ok"] or "guardrail" in resultado.get("erro", ""):
            break
        prompt += f"\n\nSua consulta anterior falhou.\nSQL: {consulta.sql}\nERRO: {resultado['erro']}\nCorrija."
    resposta = None
    if resultado["ok"]:
        resposta = texto_de(
            criar_llm("auxiliar").invoke(
                f"Responda à pergunta em português, em até 3 frases, usando SOMENTE estas linhas do banco.\n"
                f"PERGUNTA: {pergunta}\nLINHAS: {resultado['linhas'][:30]}"
            )
        )
    return {"pergunta": pergunta, "raciocinio": consulta.raciocinio, "tentativas": historico, "resultado": resultado, "resposta": resposta}
