"""Ações com efeito no mundo real, sempre com aprovação humana (human-in-the-loop).

O agente NUNCA grava diretamente. Ele só pode PROPOR um registro (`propor_registro`),
que fica pendente com um identificador. A gravação no backlog e a abertura de issues no
GitHub acontecem em `executar_registro`, chamada pela interface (CLI, notebook ou
Streamlit) depois que a pessoa confirma. Essa separação é determinística: não depende de
o LLM "obedecer" ao prompt.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime

from fabrica_agentica.config import CAMINHO_BANCO, CAMINHO_MEMORIA
from fabrica_agentica.esquemas import PlanoTrabalho
from fabrica_agentica.ferramentas import apis


def _conn_pendencias() -> sqlite3.Connection:
    CAMINHO_MEMORIA.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(CAMINHO_MEMORIA)
    conn.execute(
        """CREATE TABLE IF NOT EXISTS pendencias (
               pendencia_id TEXT PRIMARY KEY, criada_em TEXT, projeto TEXT, numero_sprint INTEGER,
               plano_json TEXT, abrir_issues INTEGER, status TEXT, resultado_json TEXT)"""
    )
    return conn


def propor_registro(plano: PlanoTrabalho, projeto: str, numero_sprint: int | None, abrir_issues: bool = True) -> dict:
    """Cria uma pendência de registro e devolve o resumo para confirmação humana."""
    pendencia_id = uuid.uuid4().hex[:8]
    with _conn_pendencias() as conn:
        conn.execute(
            "INSERT INTO pendencias VALUES (?,?,?,?,?,?,?,?)",
            (pendencia_id, datetime.now().isoformat(timespec="seconds"), projeto, numero_sprint,
             plano.model_dump_json(), int(abrir_issues), "aguardando_aprovacao", None),
        )
    return {
        "pendencia_id": pendencia_id,
        "status": "aguardando_aprovacao",
        "projeto": projeto,
        "sprint": numero_sprint,
        "historias": [f"{h.titulo} ({h.pontos} pts)" for h in plano.historias],
        "total_pontos": sum(h.pontos for h in plano.historias),
        "abrir_issues": abrir_issues,
        "mensagem": "Registro PROPOSTO. Nada foi gravado: aguarda confirmação humana na interface.",
    }


def listar_pendencias(status: str = "aguardando_aprovacao") -> list[dict]:
    with _conn_pendencias() as conn:
        conn.row_factory = sqlite3.Row
        return [dict(l) for l in conn.execute("SELECT * FROM pendencias WHERE status = ? ORDER BY criada_em", (status,))]


def rejeitar_registro(pendencia_id: str) -> None:
    with _conn_pendencias() as conn:
        conn.execute("UPDATE pendencias SET status = 'rejeitada' WHERE pendencia_id = ?", (pendencia_id,))


def executar_registro(pendencia_id: str, aprovado_por: str) -> dict:
    """Grava as histórias no backlog e abre as issues. Chamar SOMENTE após aprovação."""
    with _conn_pendencias() as conn:
        linha = conn.execute(
            "SELECT projeto, numero_sprint, plano_json, abrir_issues, status FROM pendencias WHERE pendencia_id = ?",
            (pendencia_id,),
        ).fetchone()
    if linha is None:
        raise ValueError(f"Pendência {pendencia_id} não encontrada.")
    projeto, numero_sprint, plano_json, abrir_issues, status = linha
    if status != "aguardando_aprovacao":
        raise ValueError(f"Pendência {pendencia_id} já está '{status}'.")
    plano = PlanoTrabalho.model_validate_json(plano_json)

    hoje = date.today().isoformat()
    criadas, issues = [], []
    with sqlite3.connect(CAMINHO_BANCO) as conn:  # conexão de escrita, fora do agente
        projeto_id = conn.execute("SELECT projeto_id FROM projetos WHERE lower(nome) = lower(?)", (projeto,)).fetchone()
        if projeto_id is None:
            raise ValueError(f"Projeto '{projeto}' não existe no backlog.")
        sprint = None
        if numero_sprint is not None:
            sprint = conn.execute(
                "SELECT sprint_id FROM sprints WHERE projeto_id = ? AND numero = ?", (projeto_id[0], numero_sprint)
            ).fetchone()
        for h in plano.historias:
            cursor = conn.execute(
                "INSERT INTO historias (projeto_id, sprint_id, epico, titulo, pontos, prioridade, status, responsavel_id, criado_em, updated_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (projeto_id[0], sprint[0] if sprint else None, plano.epico, h.titulo, h.pontos, "media",
                 "a_fazer" if sprint else "backlog", None, hoje, hoje),
            )
            criadas.append({"historia_id": cursor.lastrowid, "titulo": h.titulo, "pontos": h.pontos})

    if abrir_issues:
        for h, registro in zip(plano.historias, criadas):
            corpo = (
                f"**Épico:** {plano.epico}\n\n**Objetivo:** {plano.objetivo}\n\n"
                f"**Critérios de aceite**\n" + "\n".join(f"- {c}" for c in h.criterios_aceite)
                + "\n\n**Tarefas**\n" + "\n".join(f"- [ ] {t}" for t in h.tarefas)
                + f"\n\nHistória #{registro['historia_id']} do backlog · {h.pontos} pontos · aprovada por {aprovado_por}"
                + "\n\n_Gerada pelo Tech Lead Agêntico (projeto acadêmico)._"
            )
            issues.append(apis.abrir_issue_github(h.titulo[:120], corpo, rotulos=["tech-lead-agentico"]))

    resultado = {"historias_criadas": criadas, "issues": issues, "aprovado_por": aprovado_por}
    with _conn_pendencias() as conn:
        conn.execute(
            "UPDATE pendencias SET status = 'executada', resultado_json = ? WHERE pendencia_id = ?",
            (json.dumps(resultado, ensure_ascii=False), pendencia_id),
        )
    return resultado
