"""Histórico de conversa persistente em SQLite (para o RunnableWithMessageHistory).

Implementação própria de BaseChatMessageHistory (~50 linhas) em vez do
SQLChatMessageHistory do langchain-community, que exige SQLAlchemy assíncrono. As
mensagens são serializadas com `messages_to_dict`, preservando o tipo (human/ai).

Inclui a compressão da janela de contexto usada pelo agente integrador: as mensagens
recentes vão literalmente e as antigas viram um resumo progressivo (cacheado por sessão).
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from langchain_core.chat_history import BaseChatMessageHistory
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, get_buffer_string, messages_from_dict, messages_to_dict

from fabrica_agentica.config import CAMINHO_HISTORICO, criar_llm, texto_de
from fabrica_agentica.prompts import PROMPT_RESUMO_MEMORIA


class HistoricoSQLite(BaseChatMessageHistory):
    def __init__(self, sessao_id: str, caminho=CAMINHO_HISTORICO) -> None:
        self.sessao_id = sessao_id
        self.caminho = caminho
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.caminho) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS mensagens (id INTEGER PRIMARY KEY AUTOINCREMENT, sessao_id TEXT, mensagem TEXT, criado_em TEXT)")

    @property
    def messages(self) -> list[BaseMessage]:  # type: ignore[override]
        with sqlite3.connect(self.caminho) as conn:
            linhas = conn.execute("SELECT mensagem FROM mensagens WHERE sessao_id = ? ORDER BY id", (self.sessao_id,)).fetchall()
        return messages_from_dict([json.loads(l[0]) for l in linhas])

    def add_messages(self, messages: list[BaseMessage]) -> None:
        agora = datetime.now().isoformat(timespec="seconds")
        normalizadas = [AIMessage(content=texto_de(m)) if isinstance(m, AIMessage) else m for m in messages]
        with sqlite3.connect(self.caminho) as conn:
            conn.executemany(
                "INSERT INTO mensagens (sessao_id, mensagem, criado_em) VALUES (?,?,?)",
                [(self.sessao_id, json.dumps(d, ensure_ascii=False), agora) for d in messages_to_dict(normalizadas)],
            )

    def substituir_ultima_resposta(self, novo_texto: str) -> None:
        """Troca a última mensagem da IA (usado quando a verificação corrige a resposta)."""
        with sqlite3.connect(self.caminho) as conn:
            linha = conn.execute(
                "SELECT id FROM mensagens WHERE sessao_id = ? AND json_extract(mensagem, '$.type') = 'ai' ORDER BY id DESC LIMIT 1",
                (self.sessao_id,),
            ).fetchone()
            if linha:
                conn.execute("UPDATE mensagens SET mensagem = ? WHERE id = ?",
                             (json.dumps(messages_to_dict([AIMessage(content=novo_texto)])[0], ensure_ascii=False), linha[0]))

    def clear(self) -> None:
        with sqlite3.connect(self.caminho) as conn:
            conn.execute("DELETE FROM mensagens WHERE sessao_id = ?", (self.sessao_id,))


_RESUMOS: dict[tuple[str, int], str] = {}


def comprimir(mensagens: list[BaseMessage], sessao_id: str, janela: int = 6) -> list[BaseMessage]:
    """Janela deslizante + resumo: [resumo das antigas] + últimas `janela` mensagens."""
    if len(mensagens) <= janela:
        return mensagens
    corte = len(mensagens) - janela
    corte -= corte % 2  # mantém pares humano/IA
    chave = (sessao_id, corte)
    if chave not in _RESUMOS:
        anterior = max((k[1] for k in _RESUMOS if k[0] == sessao_id and k[1] < corte), default=0)
        base = _RESUMOS.get((sessao_id, anterior), "")
        novas = mensagens[anterior:corte]
        _RESUMOS[chave] = texto_de(criar_llm("auxiliar").invoke(
            PROMPT_RESUMO_MEMORIA.format(summary=base or "(vazio)", new_lines=get_buffer_string(novas))
        ))
    return [HumanMessage(content=f"[Contexto] Resumo dos turnos anteriores desta sessão: {_RESUMOS[chave]}"), *mensagens[corte:]]
