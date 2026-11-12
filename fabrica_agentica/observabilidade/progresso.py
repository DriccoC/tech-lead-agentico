"""Mensagens de progresso amigáveis para quem usa o agente.

Duas fontes de eventos:
- as ETAPAS do turno (entender o pedido, lembrar o contexto, verificar, corrigir, aprender),
  avisadas pelo próprio `TechLeadAgentico` através do atributo `ao_progresso`;
- as FERRAMENTAS chamadas pelo modelo, capturadas pelo `ProgressoCallback` (um callback do
  LangChain), que traduz o nome técnico em uma frase com os argumentos relevantes.

A interface (Streamlit) recebe tudo por uma única função `avisar(texto)`. O módulo não
depende do Streamlit, para poder ser testado e reaproveitado em outras interfaces.
"""

from __future__ import annotations

import ast
import json
from typing import Any, Callable, Optional

from langchain_core.callbacks import BaseCallbackHandler

# Etapas do turno, fora das ferramentas
ETAPAS = {
    "entender": "🧭 Entendendo o pedido (intenção e entidades)",
    "esclarecer": "❓ Falta uma informação: vou perguntar antes de seguir",
    "lembrar": "🧠 Lembrando o contexto (memórias de longo prazo)",
    "decidir": "🤔 Decidindo quais ferramentas usar",
    "verificar": "🛡️ Verificando a resposta (fatos, NLI e coerência lógica)",
    "corrigir": "↻ Rascunho reprovado: corrigindo a resposta",
    "reverificar": "🛡️ Verificando a resposta corrigida",
    "aprender": "💾 Guardando decisões e preferências na memória",
}


def _curto(texto: Any, limite: int = 60) -> str:
    texto = " ".join(str(texto).split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def mensagem_ferramenta(nome: str, args: Optional[dict] = None) -> str:
    """Traduz uma chamada de ferramenta em uma frase para o usuário."""
    a = args or {}
    if nome == "calcular_capacidade_sprint":
        alvo = "sprint" + (f" {a['numero_sprint']}" if a.get("numero_sprint") else "") + (f" do {a['projeto']}" if a.get("projeto") else "")
        sem = f", sem {', '.join(a['remover_integrantes'])}" if a.get("remover_integrantes") else ""
        return f"📅 Calculando a capacidade da {alvo}{sem} (equipe, folgas e feriados da BrasilAPI)"
    if nome == "consultar_feriados":
        return f"🗓️ Consultando os feriados de {a.get('ano', 'o ano')} na BrasilAPI"
    if nome == "consultar_backlog_sql":
        return "🗂️ Consultando o backlog (SQL somente leitura)"
    if nome == "buscar_manual_engenharia":
        return f"📘 Buscando no Manual de Engenharia: “{_curto(a.get('consulta_otimizada', ''))}”"
    if nome == "consultar_pypi":
        return f"📦 Consultando a versão mais recente de {a.get('pacote', 'a biblioteca')} no PyPI"
    if nome == "consultar_vulnerabilidades":
        return f"🔐 Checando vulnerabilidades de {a.get('pacote', 'a biblioteca')} {a.get('versao', '')} na base OSV".replace("  ", " ")
    if nome == "comparar_versoes":
        return f"🔢 Comparando as versões {a.get('versao_atual', '')} e {a.get('versao_mais_recente', '')}".strip()
    if nome == "classificar_cvss":
        return f"⚖️ Classificando a gravidade da vulnerabilidade (CVSS {a.get('pontuacao', '?')})"
    if nome == "buscar_issues_github":
        return f"🐙 Procurando issues no GitHub sobre “{_curto(a.get('termo', ''), 40)}”"
    if nome == "decompor_demanda":
        return "✍️ Criando o épico, as histórias (critérios Gherkin) e as tarefas"
    if nome == "resumir_texto_tecnico":
        return "📝 Resumindo o texto técnico"
    if nome == "propor_registro_backlog":
        return "📋 Preparando o registro no backlog (aguarda a sua aprovação)"
    return f"🔧 Usando a ferramenta {nome}"


def _argumentos(input_str: str, inputs: Optional[dict]) -> dict:
    if isinstance(inputs, dict) and inputs:
        return inputs
    for leitor in (json.loads, ast.literal_eval):
        try:
            valor = leitor(input_str)
            if isinstance(valor, dict):
                return valor
        except Exception:
            pass
    return {}


class ProgressoCallback(BaseCallbackHandler):
    """Callback do LangChain que avisa, em linguagem natural, cada ferramenta chamada."""

    run_inline = True  # roda na mesma thread do agente (a interface só aceita escrita dessa thread)

    def __init__(self, avisar: Callable[[str], None]) -> None:
        self.avisar = avisar

    def on_tool_start(self, serialized: dict, input_str: str, *, inputs: Optional[dict] = None, **kwargs: Any) -> None:
        nome = (serialized or {}).get("name") or kwargs.get("name") or "ferramenta"
        try:
            self.avisar(mensagem_ferramenta(nome, _argumentos(input_str, inputs)))
        except Exception:  # o aviso nunca pode derrubar o agente
            pass
