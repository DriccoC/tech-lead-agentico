"""Fase 5 — O agente integrador: um único agente com tudo o que foi construído.

Motor principal (exigido pela rubrica): `create_openai_tools_agent` + `AgentExecutor` com
TODAS as ferramentas (RAG, SQL, APIs, hardcoded, semânticas, ação), envolvido por
`RunnableWithMessageHistory` com histórico SQLite persistente por sessão.
Motor alternativo: a versão LangGraph (`langgraph_agente.py`), com o mesmo ciclo abaixo.

Ciclo de cada turno:
1. intenção + entidades -> estado da sessão; pergunta de esclarecimento se faltar algo;
2. memórias de longo prazo relevantes (busca vetorial + episódio mais recente);
3. agente com histórico (janela + resumo) -> rascunho de resposta + trajetória;
4. VERIFICAÇÃO (fact-check + NLI + coerência) contra as saídas das ferramentas;
5. se reprovada: uma CORREÇÃO com o feedback do verificador e nova verificação;
6. fatos duráveis -> memória de longo prazo; pendências de aprovação -> interface.
"""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.runnables import RunnableLambda, RunnablePassthrough
from langchain_core.runnables.history import RunnableWithMessageHistory

from fabrica_agentica.agentes.executor import criar_executor
from fabrica_agentica.config import criar_llm, texto_de
from fabrica_agentica.ferramentas.catalogo import TIPOS
from fabrica_agentica.memoria import intencao as fluxo
from fabrica_agentica.memoria.historico import HistoricoSQLite, comprimir
from fabrica_agentica.memoria.longo_prazo import MemoriaLongoPrazo
from fabrica_agentica.verificacao import evidencias as ev
from fabrica_agentica.verificacao.verificador import RelatorioVerificacao, feedback_para_correcao, verificar


@dataclass
class TurnoIntegrado:
    mensagem: str
    resposta: str
    motor: str
    intencao: str = "conversa_geral"
    estado_sessao: dict = field(default_factory=dict)
    memorias_usadas: list[str] = field(default_factory=list)
    trajetoria: list[dict] = field(default_factory=list)
    verificacao: Optional[RelatorioVerificacao] = None
    verificacao_rascunho: Optional[RelatorioVerificacao] = None
    resposta_rascunho: str = ""
    corrigida: bool = False
    pendencias: list[dict] = field(default_factory=list)
    pediu_esclarecimento: bool = False
    duracao_s: float = 0.0

    @property
    def ferramentas(self) -> list[str]:
        return [p["ferramenta"] for p in self.trajetoria]


def criar_executor_com_historico(janela: int = 6) -> RunnableWithMessageHistory:
    """AgentExecutor + RunnableWithMessageHistory (histórico SQLite, janela + resumo)."""
    executor = criar_executor(com_memoria_longa=True)
    cadeia = (
        RunnablePassthrough.assign(chat_history=lambda x: comprimir(x.get("chat_history", []), x["sessao_id"], janela))
        | executor
        | RunnableLambda(lambda r: {**r, "output": texto_de(r["output"])})
    )
    return RunnableWithMessageHistory(
        cadeia,
        get_session_history=lambda sessao_id: HistoricoSQLite(sessao_id),
        input_messages_key="input",
        history_messages_key="chat_history",
        output_messages_key="output",
    )


def _passos_executor(resultado: dict) -> list[dict]:
    return [{"ferramenta": a.tool, "argumentos": a.tool_input, "observacao": o if isinstance(o, str) else json.dumps(o, default=str)}
            for a, o in resultado.get("intermediate_steps", [])]


def corrigir_resposta(rascunho: str, evidencias: list[str], relatorio: RelatorioVerificacao, mensagem: str) -> str:
    """Reescreve a resposta reprovada usando só as evidências do turno (sem ferramentas)."""
    resposta = criar_llm("agente").invoke(
        "Você é o Tech Lead Agêntico. Reescreva a resposta ao usuário corrigindo os problemas apontados pela "
        "verificação, mexendo apenas no que foi apontado e mantendo o restante do rascunho. Use SOMENTE as evidências; mantenha o formato (conclusão primeiro, depois fundamentos com fonte "
        "entre parênteses) e seja coerente do começo ao fim. Responda em português do Brasil.\n\n"
        f"PERGUNTA DO USUÁRIO: {mensagem}\n\n{feedback_para_correcao(relatorio)}\n\n"
        "EVIDÊNCIAS (saídas das ferramentas):\n- " + "\n- ".join(evidencias[:150]) + f"\n\nRASCUNHO REPROVADO:\n{rascunho}"
    )
    return texto_de(resposta)


class TechLeadAgentico:
    """O agente único do projeto. `motor` = "executor" (padrão) ou "langgraph"."""

    def __init__(self, usuario: str = "adriano", sessao_id: str | None = None, motor: str = "executor",
                 verificar_respostas: bool = True, gravar_memorias: bool = True, callbacks: list | None = None) -> None:
        self.usuario = usuario
        self.sessao_id = sessao_id or f"{usuario}-{uuid.uuid4().hex[:6]}"
        self.motor = motor
        self.verificar_respostas = verificar_respostas
        self.gravar_memorias = gravar_memorias
        self.callbacks = callbacks or []
        self.memoria_longa = MemoriaLongoPrazo(escopo=usuario)
        self.historico = HistoricoSQLite(self.sessao_id)
        self.estado: dict = {}
        self.intencao_pendente: Optional[str] = None
        self.turnos: list[TurnoIntegrado] = []
        self.evidencias_sessao: list[str] = []  # tudo o que o agente observou na sessão (fonte de verdade)
        if motor == "langgraph":
            from fabrica_agentica.agentes.langgraph_agente import AgenteLangGraph

            self.langgraph = AgenteLangGraph()
        else:
            self.agente = criar_executor_com_historico()

    # ------------------------------------------------------------------ ciclo do turno
    def conversar(self, mensagem: str) -> TurnoIntegrado:
        inicio = time.perf_counter()
        ultima = self.turnos[-1].resposta if self.turnos else ""
        reconhecido = fluxo.reconhecer(mensagem, self.estado, ultima)
        if self.intencao_pendente and reconhecido.intencao == "conversa_geral":
            reconhecido.intencao = self.intencao_pendente
        self.intencao_pendente = None
        self.estado = fluxo.atualizar_estado(self.estado, reconhecido)

        perguntas = fluxo.lacunas(reconhecido.intencao, self.estado)
        if perguntas:
            resposta = " ".join(perguntas)
            self.intencao_pendente = reconhecido.intencao
            self.historico.add_user_message(mensagem)
            self.historico.add_ai_message(resposta)
            turno = TurnoIntegrado(mensagem, resposta, self.motor, reconhecido.intencao, dict(self.estado), pediu_esclarecimento=True)
            self.turnos.append(turno)
            return turno

        memorias = self.memoria_longa.recuperar(f"{mensagem} {' '.join(str(v) for v in self.estado.values())}", k=4)
        texto_memorias = MemoriaLongoPrazo.formatar(memorias)
        contexto = f"intenção atual: {reconhecido.intencao}; entidades acumuladas: {self.estado}"

        if self.motor == "langgraph":
            entrada = f"{mensagem}\n\n[Contexto da sessão: {contexto}]\n[Memórias de longo prazo: {texto_memorias}]"
            saida = self.langgraph.invocar(entrada, self.sessao_id, self.callbacks)
            rascunho, passos = saida["resposta"], saida["passos"]
            pendencias = [saida["pendente"]] if saida["pendente"] else []
        else:
            resultado = self.agente.invoke(
                {"input": mensagem, "memorias": texto_memorias, "contexto_sessao": contexto, "sessao_id": self.sessao_id},
                config={"configurable": {"session_id": self.sessao_id}, "callbacks": self.callbacks,
                        "metadata": {"usuario": self.usuario, "sessao": self.sessao_id}},
            )
            rascunho, passos = resultado["output"], _passos_executor(resultado)
            pendencias = [json.loads(p["observacao"]) for p in passos if p["ferramenta"] == "propor_registro_backlog"]

        trajetoria = [{**p, "tipo": TIPOS.get(p["ferramenta"], "ação (aprovação humana)")} for p in passos]
        self.estado.update(fluxo.entidades_da_trajetoria(trajetoria))
        turno = TurnoIntegrado(mensagem, rascunho, self.motor, reconhecido.intencao, dict(self.estado),
                               [m.conteudo for m in memorias], trajetoria, resposta_rascunho=rascunho, pendencias=pendencias)

        novas = ev.coletar([(p["ferramenta"], p["observacao"]) for p in passos])
        self.evidencias_sessao = list(dict.fromkeys(self.evidencias_sessao + novas))
        if self.verificar_respostas and self.evidencias_sessao and rascunho and (passos or reconhecido.intencao != "conversa_geral"):
            evidencias = self.evidencias_sessao + ev.regras_procedurais() + [f"Memória de sessão anterior: {m.conteudo}" for m in memorias]
            relatorio = verificar(rascunho, evidencias)
            turno.verificacao = turno.verificacao_rascunho = relatorio
            if not relatorio.aprovado:
                corrigida = corrigir_resposta(rascunho, evidencias, relatorio, mensagem)
                turno.verificacao = verificar(corrigida, evidencias)
                turno.resposta, turno.corrigida = corrigida, True
                if self.motor == "executor":
                    self.historico.substituir_ultima_resposta(corrigida)

        if self.gravar_memorias and turno.resposta:
            self.memoria_longa.extrair_e_gravar(mensagem, turno.resposta)
        turno.duracao_s = round(time.perf_counter() - inicio, 1)
        self.turnos.append(turno)
        return turno

    # ------------------------------------------------------------------ aprovação humana
    def aprovar(self, pendencia: dict, aprovado_por: str) -> dict:
        if pendencia.get("tipo") == "langgraph_hitl":
            return self.langgraph.decidir(self.sessao_id, aprovar=True, callbacks=self.callbacks)
        from fabrica_agentica.ferramentas.acoes import executar_registro

        return executar_registro(pendencia["pendencia_id"], aprovado_por)

    def rejeitar(self, pendencia: dict, motivo: str = "") -> dict:
        if pendencia.get("tipo") == "langgraph_hitl":
            return self.langgraph.decidir(self.sessao_id, aprovar=False, motivo=motivo, callbacks=self.callbacks)
        from fabrica_agentica.ferramentas.acoes import rejeitar_registro

        rejeitar_registro(pendencia["pendencia_id"])
        return {"status": "rejeitada"}

    def encerrar_sessao(self) -> Optional[dict]:
        from langchain_core.messages import get_buffer_string

        mensagens = self.historico.messages
        return self.memoria_longa.registrar_episodio(get_buffer_string(mensagens)) if mensagens else None


def turno_como_dict(turno: TurnoIntegrado) -> dict[str, Any]:
    d = {k: v for k, v in turno.__dict__.items() if k not in ("verificacao", "verificacao_rascunho")}
    d["verificacao"] = turno.verificacao.model_dump() if turno.verificacao else None
    d["verificacao_rascunho"] = turno.verificacao_rascunho.model_dump() if turno.verificacao_rascunho else None
    return d
