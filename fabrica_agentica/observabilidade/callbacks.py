"""Callbacks de logging e depuração (complementam o rastreamento do LangSmith).

`RegistroExecucao` grava, em JSON Lines (logs/execucoes.jsonl), cada início e fim de
chamada ao LLM e de ferramenta, com duração, tokens e erros. Também guarda os eventos
em memória para inspeção no notebook ou no painel do Streamlit.

Por que além do LangSmith: o log local funciona sem conta nem rede (modo demo), é
auditável pelo professor e alimenta a "trajetória" mostrada na interface.
"""

from __future__ import annotations

import json
import time
from datetime import datetime
from typing import Any, Optional
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler

from fabrica_agentica.config import CAMINHO_LOGS


class RegistroExecucao(BaseCallbackHandler):
    def __init__(self, arquivo: str = "execucoes.jsonl", imprimir: bool = False, sessao: str = "") -> None:
        self.caminho = CAMINHO_LOGS / arquivo
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        self.imprimir = imprimir
        self.sessao = sessao
        self.eventos: list[dict] = []
        self._inicios: dict[UUID, float] = {}

    # ------------------------------------------------------------------ utilitário
    def _registrar(self, evento: dict) -> None:
        evento = {"ts": datetime.now().isoformat(timespec="milliseconds"), "sessao": self.sessao, **evento}
        self.eventos.append(evento)
        with self.caminho.open("a", encoding="utf-8") as f:
            f.write(json.dumps(evento, ensure_ascii=False, default=str) + "\n")
        if self.imprimir:
            detalhe = evento.get("ferramenta") or evento.get("modelo") or ""
            extra = f" {evento['duracao_s']}s" if "duracao_s" in evento else ""
            print(f"  [log] {evento['tipo']:<12} {detalhe}{extra} {str(evento.get('entrada') or evento.get('saida') or evento.get('erro') or '')[:100]}")

    def _duracao(self, run_id: UUID) -> float:
        return round(time.perf_counter() - self._inicios.pop(run_id, time.perf_counter()), 2)

    # ------------------------------------------------------------------ LLM
    def on_chat_model_start(self, serialized: dict, messages: list, *, run_id: UUID, **kwargs: Any) -> None:
        self._inicios[run_id] = time.perf_counter()
        modelo = (kwargs.get("metadata") or {}).get("ls_model_name") or (serialized or {}).get("name")
        self._registrar({"tipo": "llm_inicio", "modelo": modelo, "n_mensagens": sum(len(m) for m in messages)})

    def on_llm_end(self, response: Any, *, run_id: UUID, **kwargs: Any) -> None:
        uso: dict = {}
        try:
            msg = response.generations[0][0].message
            uso = dict(getattr(msg, "usage_metadata", None) or {})
            chamadas = [tc["name"] for tc in getattr(msg, "tool_calls", []) or []]
        except (AttributeError, IndexError):
            chamadas = []
        self._registrar({"tipo": "llm_fim", "duracao_s": self._duracao(run_id), "tokens": uso, "decidiu_chamar": chamadas})

    def on_llm_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._registrar({"tipo": "llm_erro", "duracao_s": self._duracao(run_id), "erro": repr(error)[:300]})

    # ------------------------------------------------------------------ ferramentas
    def on_tool_start(self, serialized: dict, input_str: str, *, run_id: UUID, **kwargs: Any) -> None:
        self._inicios[run_id] = time.perf_counter()
        self._registrar({"tipo": "tool_inicio", "ferramenta": (serialized or {}).get("name"), "entrada": input_str[:500]})

    def on_tool_end(self, output: Any, *, run_id: UUID, **kwargs: Any) -> None:
        conteudo = getattr(output, "content", output)
        self._registrar({"tipo": "tool_fim", "ferramenta": kwargs.get("name"), "duracao_s": self._duracao(run_id), "saida": str(conteudo)[:500]})

    def on_tool_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._registrar({"tipo": "tool_erro", "ferramenta": kwargs.get("name"), "duracao_s": self._duracao(run_id), "erro": repr(error)[:300]})

    # ------------------------------------------------------------------ agente clássico
    def on_agent_action(self, action: Any, *, run_id: UUID, parent_run_id: Optional[UUID] = None, **kwargs: Any) -> None:
        self._registrar({"tipo": "decisao", "ferramenta": action.tool, "entrada": str(action.tool_input)[:300]})

    def on_agent_finish(self, finish: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._registrar({"tipo": "resposta", "saida": str(finish.return_values.get("output"))[:300]})

    # ------------------------------------------------------------------ resumo
    def resumo(self) -> dict:
        llm = [e for e in self.eventos if e["tipo"] == "llm_fim"]
        tools = [e for e in self.eventos if e["tipo"] == "tool_fim"]
        return {
            "chamadas_llm": len(llm),
            "tokens_entrada": sum(e["tokens"].get("input_tokens", 0) for e in llm),
            "tokens_saida": sum(e["tokens"].get("output_tokens", 0) for e in llm),
            "ferramentas": [e["ferramenta"] for e in tools],
            "erros": [e for e in self.eventos if e["tipo"].endswith("erro")],
            "tempo_llm_s": round(sum(e["duracao_s"] for e in llm), 2),
            "tempo_ferramentas_s": round(sum(e["duracao_s"] for e in tools), 2),
        }
