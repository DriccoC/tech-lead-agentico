"""Versão LangGraph do Tech Lead Agêntico (base para a próxima disciplina, multiagente).

- `create_agent` (LangChain 1.x, roda sobre um grafo LangGraph);
- persistência por `thread_id` com `SqliteSaver` (o histórico é o próprio estado do grafo);
- aprovação humana NATIVA com `HumanInTheLoopMiddleware`: a ferramenta de escrita
  `registrar_no_backlog` grava de fato, mas o grafo PAUSA (interrupt) antes de executá-la e
  só continua com `Command(resume=...)` — aprovar, editar ou rejeitar.

Diferença em relação ao AgentExecutor: lá a escrita é separada em "propor" (ferramenta) e
"executar" (fora do agente); aqui a própria execução da ferramenta é interrompida pelo grafo.
"""

from __future__ import annotations

import json
import sqlite3
from typing import Optional

from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from fabrica_agentica.config import DADOS, criar_llm, texto_de
from fabrica_agentica.esquemas import PlanoTrabalho
from fabrica_agentica.ferramentas import acoes
from fabrica_agentica.ferramentas.catalogo import FERRAMENTAS, ArgsRegistro
from fabrica_agentica.prompts import system_com_exemplos

CAMINHO_CHECKPOINTS = DADOS / "checkpoints.db"


@tool(args_schema=ArgsRegistro)
def registrar_no_backlog(projeto: str, plano: PlanoTrabalho, numero_sprint: Optional[int] = None, abrir_issues: bool = True) -> str:
    """Registra as histórias do plano no backlog e abre as issues no GitHub. Esta ferramenta GRAVA de verdade e
    por isso exige aprovação humana: a execução pausa até a pessoa aprovar. Use só quando o usuário pedir."""
    if isinstance(plano, dict):
        plano = PlanoTrabalho.model_validate(plano)
    pendencia = acoes.propor_registro(plano, projeto, numero_sprint, abrir_issues)
    resultado = acoes.executar_registro(pendencia["pendencia_id"], aprovado_por="aprovação humana (LangGraph HITL)")
    return json.dumps(resultado, ensure_ascii=False, default=str)


def ferramentas_langgraph() -> list:
    return [f for f in FERRAMENTAS if f.name != "propor_registro_backlog"] + [registrar_no_backlog]


SISTEMA_LANGGRAPH = system_com_exemplos().replace(
    "5. Registro no backlog e abertura de issues: só use propor_registro_backlog quando o usuário pedir; isso NÃO "
    "grava nada, apenas cria uma pendência para confirmação humana.",
    "5. Registro no backlog e abertura de issues: use registrar_no_backlog só quando o usuário pedir; a execução "
    "pausa para aprovação humana antes de gravar.",
)


class AgenteLangGraph:
    def __init__(self) -> None:
        self.conexao = sqlite3.connect(CAMINHO_CHECKPOINTS, check_same_thread=False)
        self.checkpointer = SqliteSaver(self.conexao)
        self.grafo = create_agent(
            model=criar_llm("agente"),
            tools=ferramentas_langgraph(),
            system_prompt=SISTEMA_LANGGRAPH,
            checkpointer=self.checkpointer,
            middleware=[HumanInTheLoopMiddleware(interrupt_on={"registrar_no_backlog": True})],
        )

    @staticmethod
    def _config(thread_id: str, callbacks: list | None = None) -> dict:
        return {"configurable": {"thread_id": thread_id}, "callbacks": callbacks or [], "recursion_limit": 40}

    def _resultado(self, estado: dict, inicio: int) -> dict:
        mensagens = estado["messages"]
        novas = mensagens[inicio:]
        passos, chamadas = [], {}
        for m in novas:
            if isinstance(m, AIMessage):
                for tc in m.tool_calls or []:
                    chamadas[tc["id"]] = tc
            elif isinstance(m, ToolMessage):
                tc = chamadas.get(m.tool_call_id, {})
                passos.append({"ferramenta": m.name or tc.get("name"), "argumentos": tc.get("args", {}), "observacao": texto_de(m) or str(m.content)})
        interrupcao = estado.get("__interrupt__")
        pendente = None
        if interrupcao:
            valor = interrupcao[0].value
            pendente = {"tipo": "langgraph_hitl", "requisicao": json.loads(json.dumps(valor, default=lambda o: getattr(o, "__dict__", str(o))))}
        ultima = mensagens[-1] if mensagens else None
        resposta = texto_de(ultima) if isinstance(ultima, AIMessage) and not pendente else ""
        return {"resposta": resposta, "passos": passos, "pendente": pendente}

    def invocar(self, mensagem: str, thread_id: str, callbacks: list | None = None) -> dict:
        config = self._config(thread_id, callbacks)
        anterior = self.grafo.get_state(config).values.get("messages", [])
        estado = self.grafo.invoke({"messages": [HumanMessage(content=mensagem)]}, config=config, version="v1")
        return self._resultado(estado, len(anterior))

    def decidir(self, thread_id: str, aprovar: bool, motivo: str = "", callbacks: list | None = None) -> dict:
        """Retoma o grafo pausado: aprova (executa a gravação) ou rejeita (o agente é informado)."""
        config = self._config(thread_id, callbacks)
        anterior = self.grafo.get_state(config).values.get("messages", [])
        decisao = {"type": "approve"} if aprovar else {"type": "reject", "message": motivo or "Registro rejeitado pela pessoa revisora."}
        estado = self.grafo.invoke(Command(resume={"decisions": [decisao]}), config=config, version="v1")
        return self._resultado(estado, len(anterior))
