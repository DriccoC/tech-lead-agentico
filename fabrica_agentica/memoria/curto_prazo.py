"""Memória de curto prazo: ConversationBufferMemory com janela deslizante + resumo.

Mantém as últimas `janela` mensagens literalmente e, quando a conversa passa disso, as
mensagens mais antigas são incorporadas a um RESUMO progressivo (feito pelo LLM
auxiliar com o PROMPT_RESUMO_MEMORIA, que preserva projeto, sprint, pessoas e números).
O agente recebe: [resumo dos turnos antigos] + [mensagens recentes].

É uma subclasse de ConversationBufferMemory (o buffer guarda a conversa inteira, útil
para auditoria e para o episódio de longo prazo), mudando apenas o que é ENTREGUE ao
prompt — que é o que controla o tamanho da janela de contexto.
"""

from __future__ import annotations

from typing import Any

from langchain_classic.memory import ConversationBufferMemory
from langchain_core.messages import BaseMessage, HumanMessage, get_buffer_string

from fabrica_agentica.config import criar_llm, texto_de
from fabrica_agentica.prompts import PROMPT_RESUMO_MEMORIA


class MemoriaJanelaResumo(ConversationBufferMemory):
    janela: int = 6  # mensagens (3 turnos) mantidas literalmente
    resumo: str = ""
    resumidas: int = 0  # quantas mensagens do buffer já entraram no resumo

    def __init__(self, **kwargs: Any) -> None:
        kwargs.setdefault("memory_key", "chat_history")
        kwargs.setdefault("return_messages", True)
        kwargs.setdefault("input_key", "input")
        kwargs.setdefault("output_key", "output")
        super().__init__(**kwargs)

    def _atualizar_resumo(self) -> None:
        mensagens = self.chat_memory.messages
        limite = max(len(mensagens) - self.janela, 0)
        if limite <= self.resumidas:
            return
        novas = mensagens[self.resumidas:limite]
        prompt = PROMPT_RESUMO_MEMORIA.format(summary=self.resumo or "(vazio)", new_lines=get_buffer_string(novas))
        self.resumo = texto_de(criar_llm("auxiliar").invoke(prompt))
        self.resumidas = limite

    def save_context(self, inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
        super().save_context(inputs, outputs)
        self._atualizar_resumo()

    def mensagens_para_prompt(self) -> list[BaseMessage]:
        recentes = self.chat_memory.messages[self.resumidas:]
        if self.resumo:
            # Como mensagem humana de contexto (e não SystemMessage): a API da Anthropic só aceita
            # mensagens de sistema no início, e o histórico entra depois dos exemplos few-shot.
            return [HumanMessage(content=f"[Contexto] Resumo dos turnos anteriores desta sessão: {self.resumo}"), *recentes]
        return list(recentes)

    def load_memory_variables(self, inputs: dict[str, Any]) -> dict[str, Any]:
        return {self.memory_key: self.mensagens_para_prompt()}

    def clear(self) -> None:
        super().clear()
        self.resumo, self.resumidas = "", 0
