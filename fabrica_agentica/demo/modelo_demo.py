"""Modelo de chat FALSO e roteirizado para o modo demonstração (sem chave, sem custo).

Atende ao requisito do enunciado de oferecer "alternativas dummy funcionais" para o
professor. Ele NÃO é inteligente: segue regras por palavras-chave, mas fala os mesmos
"protocolos" de um LLM real, para que todo o sistema rode de ponta a ponta:

- chamada de ferramentas (`bind_tools` -> AIMessage.tool_calls), em várias rodadas;
- formato texto do ReAct clássico (Thought / Action / Action Input / Final Answer);
- roteamento do RouterChain (bloco JSON com destination/next_inputs);
- saída estruturada (`with_structured_output`) e JSON para PydanticOutputParser;
- streaming token a token.
"""

from __future__ import annotations

import json
import re
from typing import Any, Iterator, Optional

from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import RunnableLambda

from fabrica_agentica.demo import roteiro


def _conteudo(msg: Any) -> str:
    c = getattr(msg, "content", msg)
    if isinstance(c, list):
        return " ".join(b.get("text", "") if isinstance(b, dict) else str(b) for b in c)
    return str(c)


def _texto_entrada(entrada: Any) -> str:
    if isinstance(entrada, str):
        return entrada
    if isinstance(entrada, list):
        return "\n".join(_conteudo(m) for m in entrada)
    if hasattr(entrada, "to_messages"):
        return "\n".join(_conteudo(m) for m in entrada.to_messages())
    if isinstance(entrada, dict):
        return json.dumps(entrada, ensure_ascii=False)
    return str(entrada)


class ModeloDemo(BaseChatModel):
    """LLM roteirizado. Ver demo/roteiro.py para as regras de decisão."""

    nomes_ferramentas: list[str] = []

    @property
    def _llm_type(self) -> str:
        return "modelo-demo-roteirizado"

    # ------------------------------------------------------------------ ferramentas
    def bind_tools(self, tools: Any, **kwargs: Any):  # type: ignore[override]
        nomes = []
        for t in tools:
            if isinstance(t, dict):
                nomes.append(t.get("name") or t.get("function", {}).get("name"))
            else:
                nomes.append(getattr(t, "name", str(t)))
        return self.model_copy(update={"nomes_ferramentas": [n for n in nomes if n]})

    def bind(self, **kwargs: Any):  # usado por create_openai_tools_agent
        if "tools" in kwargs:
            return self.bind_tools(kwargs["tools"])
        return self

    def with_structured_output(self, schema: Any, **kwargs: Any):  # type: ignore[override]
        return RunnableLambda(lambda entrada: roteiro.estruturar(schema, _texto_entrada(entrada)))

    # ------------------------------------------------------------------ geração
    def _decidir(self, messages: list[BaseMessage]) -> AIMessage:
        prompt_completo = "\n".join(_conteudo(m) for m in messages)

        if "next_inputs" in prompt_completo and "destination" in prompt_completo:
            return AIMessage(content=roteiro.rotear(prompt_completo))

        if "Action Input" in prompt_completo and "Final Answer" in prompt_completo:
            return AIMessage(content=roteiro.passo_react(prompt_completo))

        esquema = roteiro.esquema_em_instrucoes(prompt_completo)
        if esquema is not None:
            humano = roteiro.ultimo_texto_usuario(prompt_completo)
            return AIMessage(content=json.dumps(roteiro.estruturar(esquema, humano).model_dump(), ensure_ascii=False))

        if self.nomes_ferramentas:
            return roteiro.passo_ferramentas(messages, self.nomes_ferramentas)

        return AIMessage(content=roteiro.resposta_conversa(messages))

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> ChatResult:
        resposta = self._decidir(messages)
        resposta.usage_metadata = {"input_tokens": sum(len(_conteudo(m)) // 4 for m in messages), "output_tokens": len(_conteudo(resposta)) // 4, "total_tokens": 0}
        resposta.usage_metadata["total_tokens"] = resposta.usage_metadata["input_tokens"] + resposta.usage_metadata["output_tokens"]
        return ChatResult(generations=[ChatGeneration(message=resposta)])

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: Optional[list[str]] = None,
        run_manager: Optional[CallbackManagerForLLMRun] = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        resposta = self._decidir(messages)
        if resposta.tool_calls:
            yield ChatGenerationChunk(message=AIMessageChunk(content="", tool_call_chunks=[
                {"name": tc["name"], "args": json.dumps(tc["args"], ensure_ascii=False), "id": tc["id"], "index": i}
                for i, tc in enumerate(resposta.tool_calls)
            ]))
            return
        for pedaco in re.findall(r"\S+\s*", _conteudo(resposta)):
            chunk = ChatGenerationChunk(message=AIMessageChunk(content=pedaco))
            if run_manager:
                run_manager.on_llm_new_token(pedaco, chunk=chunk)
            yield chunk


__all__ = ["ModeloDemo", "HumanMessage", "ToolMessage"]
