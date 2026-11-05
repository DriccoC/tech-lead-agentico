"""Fase 3 — Chatbot conversacional: agente + memória de curto e longo prazo.

Ciclo de cada turno:
1. reconhece intenção e entidades e atualiza o ESTADO DA SESSÃO;
2. se o fluxo da intenção exige uma entidade ausente, pergunta (sem chamar o agente);
3. recupera memórias de longo prazo relevantes (busca vetorial);
4. chama o agente (AgentExecutor) com memória de curto prazo (janela + resumo),
   memórias de longo prazo e estado da sessão no prompt;
5. extrai fatos duráveis do turno e grava/atualiza na memória de longo prazo.
Ao encerrar a sessão, um resumo vira memória EPISÓDICA.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from langchain_core.messages import get_buffer_string

from fabrica_agentica.agentes.executor import criar_executor, trajetoria
from fabrica_agentica.config import texto_de
from fabrica_agentica.memoria import intencao as fluxo
from fabrica_agentica.memoria.curto_prazo import MemoriaJanelaResumo
from fabrica_agentica.memoria.longo_prazo import MemoriaLongoPrazo


@dataclass
class Turno:
    mensagem: str
    resposta: str
    intencao: str
    entidades: dict
    estado_sessao: dict
    memorias_usadas: list[str] = field(default_factory=list)
    memorias_gravadas: list[dict] = field(default_factory=list)
    trajetoria: list[dict] = field(default_factory=list)
    pediu_esclarecimento: bool = False


class ChatbotTechLead:
    def __init__(self, usuario: str = "adriano", janela: int = 6, callbacks: list | None = None, gravar_memorias: bool = True) -> None:
        self.usuario = usuario
        self.sessao_id = uuid.uuid4().hex[:8]
        self.memoria_curta = MemoriaJanelaResumo(janela=janela)
        self.memoria_longa = MemoriaLongoPrazo(escopo=usuario)
        self.executor = criar_executor(memoria=self.memoria_curta, com_memoria_longa=True)
        self.estado: dict = {}
        self.callbacks = callbacks or []
        self.gravar_memorias = gravar_memorias
        self.turnos: list[Turno] = []
        self.intencao_pendente: str | None = None  # intenção que aguardava esclarecimento

    def conversar(self, mensagem: str) -> Turno:
        ultima = self.turnos[-1].resposta if self.turnos else ""
        reconhecido = fluxo.reconhecer(mensagem, self.estado, ultima)
        if self.intencao_pendente and reconhecido.intencao == "conversa_geral":
            # a mensagem é a resposta a uma pergunta de esclarecimento: retoma o fluxo pendente
            reconhecido.intencao = self.intencao_pendente
        self.intencao_pendente = None
        self.estado = fluxo.atualizar_estado(self.estado, reconhecido)
        entidades = {k: v for k, v in reconhecido.model_dump().items() if k != "intencao" and v is not None}

        perguntas = fluxo.lacunas(reconhecido.intencao, self.estado)
        if perguntas:
            resposta = " ".join(perguntas)
            self.intencao_pendente = reconhecido.intencao
            self.memoria_curta.save_context({"input": mensagem}, {"output": resposta})
            turno = Turno(mensagem, resposta, reconhecido.intencao, entidades, dict(self.estado), pediu_esclarecimento=True)
            self.turnos.append(turno)
            return turno

        consulta_memoria = f"{mensagem} {' '.join(str(v) for v in self.estado.values())}"
        memorias = self.memoria_longa.recuperar(consulta_memoria, k=4)
        contexto = f"intenção atual: {reconhecido.intencao}; entidades acumuladas: {self.estado}"
        resultado = self.executor.invoke(
            {"input": mensagem, "memorias": MemoriaLongoPrazo.formatar(memorias), "contexto_sessao": contexto},
            config={"callbacks": self.callbacks, "metadata": {"sessao": self.sessao_id, "usuario": self.usuario}},
        )
        resposta = texto_de(resultado["output"])
        self.estado.update(fluxo.entidades_da_trajetoria(trajetoria(resultado)))
        gravadas = self.memoria_longa.extrair_e_gravar(mensagem, resposta) if self.gravar_memorias else []
        turno = Turno(
            mensagem, resposta, reconhecido.intencao, entidades, dict(self.estado),
            memorias_usadas=[m.conteudo for m in memorias], memorias_gravadas=gravadas, trajetoria=trajetoria(resultado),
        )
        self.turnos.append(turno)
        return turno

    def encerrar_sessao(self) -> dict | None:
        """Registra a sessão como memória episódica."""
        if not self.turnos:
            return None
        return self.memoria_longa.registrar_episodio(get_buffer_string(self.memoria_curta.chat_memory.messages))
