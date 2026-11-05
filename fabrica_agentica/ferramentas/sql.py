"""Padrão text-to-query: o LLM traduz a pergunta em SQL sobre o backlog (SQLite).

Guardrails, em camadas:
1. A conexão do agente é aberta em modo SOMENTE LEITURA (URI `?mode=ro`): mesmo que
   um comando de escrita passe pelo filtro, o próprio SQLite o recusa.
2. Filtro de comando: só aceita uma instrução que comece com SELECT ou WITH, e recusa
   palavras proibidas comparando PALAVRAS INTEIRAS (assim `updated_at` não é bloqueado
   por conter "UPDATE", problema do guardrail da Aula 6).
3. Limite de linhas (LIMIT 50) para não estourar o contexto do LLM.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from fabrica_agentica.config import CAMINHO_BANCO

PALAVRAS_PROIBIDAS = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER", "CREATE", "REPLACE", "TRUNCATE", "ATTACH", "DETACH", "PRAGMA", "VACUUM")
LIMITE_LINHAS = 50

DICIONARIO_DADOS = """
Banco de backlog da NovaForja Software (SQLite). Tabelas e colunas:
- projetos(projeto_id, nome, descricao, stack, repositorio)  -- nomes: 'Portal', 'PagaFacil', 'AppCampo'
- desenvolvedores(dev_id, nome, papel, senioridade)
- sprints(sprint_id, projeto_id, numero, inicio, fim, status)  -- status: concluida | em_andamento | planejada; datas AAAA-MM-DD
- alocacoes(sprint_id, dev_id, fator_foco, dias_ausencia)  -- quem está em cada sprint
- historias(historia_id, projeto_id, sprint_id, epico, titulo, pontos, prioridade, status, responsavel_id, criado_em, updated_at)
    -- sprint_id NULL = backlog sem sprint; status: backlog | a_fazer | em_andamento | concluida; prioridade: alta | media | baixa
- bugs(bug_id, projeto_id, titulo, severidade, status, aberto_em)  -- severidade: critica | alta | media | baixa
Relacionamentos: sprints.projeto_id -> projetos; historias.sprint_id -> sprints; alocacoes liga sprints e desenvolvedores.
Observação: 'sprints.numero' é o número exibido ao time (ex.: sprint 13 do Portal); 'sprint_id' é a chave interna.
""".strip()


class ConsultaRecusada(ValueError):
    """Consulta bloqueada pelo guardrail."""


def validar_consulta(consulta: str) -> str:
    """Aplica o guardrail e devolve a consulta normalizada (com LIMIT)."""
    sql = consulta.strip().rstrip(";").strip()
    if ";" in sql:
        raise ConsultaRecusada("Apenas uma instrução SQL por consulta.")
    if not re.match(r"^(SELECT|WITH)\b", sql, flags=re.IGNORECASE):
        raise ConsultaRecusada("Somente consultas de leitura (SELECT/WITH) são permitidas.")
    sem_textos = re.sub(r"'[^']*'", "''", sql)  # palavras dentro de literais não contam
    for palavra in PALAVRAS_PROIBIDAS:
        if re.search(rf"\b{palavra}\b", sem_textos, flags=re.IGNORECASE):
            raise ConsultaRecusada(f"Comando proibido detectado: {palavra}.")
    if not re.search(r"\bLIMIT\s+\d+", sem_textos, flags=re.IGNORECASE):
        sql = f"{sql} LIMIT {LIMITE_LINHAS}"
    return sql


def conexao_leitura(caminho: Path = CAMINHO_BANCO) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def executar_consulta(consulta: str, caminho: Path = CAMINHO_BANCO) -> dict:
    """Executa a consulta validada e devolve linhas como dicionários (ou o erro)."""
    try:
        sql = validar_consulta(consulta)
    except ConsultaRecusada as erro:
        return {"ok": False, "erro": f"Consulta recusada pelo guardrail: {erro}", "sql": consulta}
    try:
        with conexao_leitura(caminho) as conn:
            linhas = [dict(l) for l in conn.execute(sql).fetchall()]
    except sqlite3.Error as erro:
        return {"ok": False, "erro": f"Erro de SQL: {erro}. Revise nomes de tabelas e colunas.", "sql": sql}
    return {"ok": True, "sql": sql, "total": len(linhas), "linhas": linhas}
