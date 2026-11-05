"""Configuração central do Tech Lead Agêntico.

Tudo o que depende de ambiente fica aqui: chaves (lidas do .env, nunca escritas no
código), escolha do provedor de LLM, modelo de embeddings e caminhos dos dados.

Provedores (variável LLM_PROVIDER):
- "anthropic" (padrão): Claude via langchain-anthropic.
- "openai": alternativa para quem só tem chave da OpenAI (ex.: o professor).
- "demo": modelo falso roteirizado, sem chave e sem custo (ver demo/modelo_demo.py).
Se LLM_PROVIDER não for definido e não houver ANTHROPIC_API_KEY, cai no modo demo.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
load_dotenv(RAIZ / ".env")

DADOS = RAIZ / "dados"
CAMINHO_BANCO = DADOS / "backlog.db"
CAMINHO_MANUAL = DADOS / "manual"
CAMINHO_INDICE = DADOS / "indice_faiss"
CAMINHO_MEMORIA = DADOS / "memoria.db"
CAMINHO_HISTORICO = DADOS / "historico_conversas.db"
CAMINHO_LOGS = RAIZ / "logs"
CAMINHO_FIXTURES = Path(__file__).resolve().parent / "demo" / "fixtures"

MODELO_EMBEDDINGS = os.getenv(
    "MODELO_EMBEDDINGS", "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
)
MODELO_NLI = os.getenv("MODELO_NLI", "MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7")

GITHUB_REPO = os.getenv("GITHUB_REPO", "")  # ex.: "usuario/fabrica-agentica-sandbox"


def provedor() -> str:
    """Devolve o provedor de LLM em uso: anthropic, openai ou demo."""
    escolhido = os.getenv("LLM_PROVIDER", "").strip().lower()
    if escolhido in {"anthropic", "openai", "demo"}:
        return escolhido
    return "anthropic" if os.getenv("ANTHROPIC_API_KEY") else "demo"


def modo_demo() -> bool:
    return provedor() == "demo"


def apis_offline() -> bool:
    """APIs externas usam respostas gravadas (fixtures) em vez da rede.

    Ligado automaticamente no modo demo; pode ser forçado com APIS_OFFLINE=1.
    """
    valor = os.getenv("APIS_OFFLINE")
    if valor is not None:
        return valor.strip() in {"1", "true", "sim"}
    return modo_demo()


# --------------------------------------------------------------------------------------
# Adaptador do Claude para construtos "OpenAI tools" do LangChain clássico
# --------------------------------------------------------------------------------------
def _criar_classe_claude():
    from langchain_anthropic import ChatAnthropic
    from langchain_anthropic.chat_models import convert_to_anthropic_tool

    class ChatClaudeCompat(ChatAnthropic):
        """ChatAnthropic que aceita ferramentas no formato OpenAI.

        `create_openai_tools_agent` (exigido pela rubrica) faz
        `llm.bind(tools=[convert_to_openai_tool(t)])`, ou seja, envia as ferramentas no
        formato {"type": "function", "function": {...}}. A API da Anthropic recusa esse
        formato; aqui convertemos para o formato nativo antes de montar a requisição.
        O resto do fluxo (tool_calls -> OpenAIToolsAgentOutputParser) já é agnóstico.
        """

        def _get_request_payload(self, input_: Any, *, stop: Any = None, **kwargs: Any) -> dict:
            ferramentas = kwargs.get("tools")
            if ferramentas:
                kwargs["tools"] = [
                    convert_to_anthropic_tool(f)
                    if isinstance(f, dict) and f.get("type") == "function"
                    else f
                    for f in ferramentas
                ]
            return super()._get_request_payload(input_, stop=stop, **kwargs)

    return ChatClaudeCompat


@lru_cache(maxsize=8)
def criar_llm(papel: str = "agente"):
    """Cria o modelo de chat para um papel do sistema.

    Papéis: "agente" (raciocínio e ferramentas), "auxiliar" (tarefas curtas: extração,
    intenção, resumo) e "juiz" (avaliação). Modelos configuráveis no .env.
    """
    escolhido = provedor()
    if escolhido == "demo":
        from fabrica_agentica.demo.modelo_demo import ModeloDemo

        return ModeloDemo()

    if escolhido == "openai":
        from langchain_openai import ChatOpenAI

        modelo = os.getenv(f"OPENAI_MODEL_{papel.upper()}", os.getenv("OPENAI_MODEL", "gpt-4o"))
        return ChatOpenAI(model=modelo, temperature=0)

    padrao = {"agente": "claude-sonnet-5-5", "auxiliar": "claude-haiku-5-5", "juiz": "claude-sonnet-5-5"}
    modelo = os.getenv(f"ANTHROPIC_MODEL_{papel.upper()}", padrao.get(papel, "claude-sonnet-5-5"))
    esforco = os.getenv("ANTHROPIC_EFFORT", "low")
    classe = _criar_classe_claude()
    # URL explícita: evita herdar um ANTHROPIC_BASE_URL do ambiente (ex.: ferramentas que rodam
    # o projeto dentro de outro cliente), o que mandaria a chave do .env para outro servidor.
    url_api = os.getenv("PROJETO_ANTHROPIC_API_URL", "https://api.anthropic.com")
    # Raciocínio adaptativo com "drop_block": os blocos de thinking ficam vinculados ao contexto em que
    # foram gerados; quando o AgentExecutor clássico remonta o prompt, um bloco antigo pode não bater
    # com o novo prefixo. Em vez de erro 400, a API descarta o bloco (beta thinking-binding-controls).
    return classe(
        model=modelo,
        effort=esforco,
        max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", "4096")),
        anthropic_api_url=url_api,
        api_key=os.getenv("ANTHROPIC_API_KEY"),
        thinking={"type": "adaptive", "block_binding": {"prefix_mismatch_behavior": "drop_block"}},
        betas=["thinking-binding-controls-2026-08-01"],
    )


def texto_de(resposta: Any) -> str:
    """Extrai o texto de uma resposta de LLM, qualquer que seja o provedor.

    Com Claude, `content` é uma lista de blocos (texto, raciocínio, tool_use); com a
    OpenAI é uma string. Use sempre esta função em vez de ler `.content` diretamente.
    """
    if resposta is None:
        return ""
    if isinstance(resposta, str):
        return resposta
    if isinstance(resposta, dict) and "output" in resposta:
        return texto_de(resposta["output"])
    if isinstance(resposta, list):
        partes = []
        for bloco in resposta:
            if isinstance(bloco, str):
                partes.append(bloco)
            elif isinstance(bloco, dict) and bloco.get("type") == "text":
                partes.append(bloco.get("text", ""))
        return "".join(partes).strip()
    texto = getattr(resposta, "text", None)
    if isinstance(texto, str):
        return texto.strip()
    if callable(texto):  # versões antigas: .text() era método
        return str(texto()).strip()
    return texto_de(getattr(resposta, "content", ""))


@lru_cache(maxsize=1)
def criar_embeddings():
    """Embeddings locais e gratuitos (Hugging Face), sem chave de API.

    A Anthropic não oferece modelo de embeddings; um modelo multilíngue local mantém o
    projeto reprodutível pelo professor sem credenciais extras.
    """
    from langchain_huggingface import HuggingFaceEmbeddings

    return HuggingFaceEmbeddings(
        model_name=MODELO_EMBEDDINGS,
        encode_kwargs={"normalize_embeddings": True},
    )


def descrever_ambiente() -> str:
    """Resumo legível da configuração atual (útil no topo dos notebooks)."""
    linhas = [
        f"Provedor de LLM : {provedor()}",
        f"APIs externas   : {'respostas gravadas (offline)' if apis_offline() else 'rede (ao vivo)'}",
        f"Embeddings      : {MODELO_EMBEDDINGS}",
        f"Modelo NLI      : {MODELO_NLI}",
        f"LangSmith       : {'ligado' if os.getenv('LANGSMITH_TRACING', '').lower() == 'true' and os.getenv('LANGSMITH_API_KEY') else 'desligado'}",
        f"Repositório GH  : {GITHUB_REPO or '(não configurado: issues no modo simulado)'}",
    ]
    return "\n".join(linhas)
