"""Avaliação do agente integrador como SISTEMA: qualidade das respostas e trajetória.

- Dataset com 19 casos (planejamento, capacidade, SQL, dependências, RAG difícil, fora de
  escopo, APIs, memória multi-turno, conversa e um caso adversarial para o verificador).
- Avaliadores:
  * cobertura_trajetoria: fração das ferramentas esperadas que foram chamadas;
  * trajetoria_exata: o conjunto de ferramentas chamadas é exatamente o esperado;
  * corretude: juiz LLM com SAÍDA ESTRUTURADA (booleano + nota + justificativa) — sem o bug
    da Aula 8 em que "CORRETO" in "INCORRETO" dava nota 1 sempre;
  * verificacao_final / verificacao_rascunho: a camada de V&V aprovou a resposta final / o
    rascunho; `corrigida` indica que a autocorreção entrou em ação.
- Execução no LangSmith (`evaluate`) ou, sem chave, local com os mesmos avaliadores.
"""

from __future__ import annotations

import os
from typing import Any

from pydantic import BaseModel, Field

from fabrica_agentica.config import criar_llm

CASOS: list[dict[str, Any]] = [
    {"input": "Quero login com Google no projeto Portal na próxima sprint.",
     "ferramentas": ["calcular_capacidade_sprint", "buscar_manual_engenharia", "consultar_pypi", "consultar_vulnerabilidades", "decompor_demanda"],
     "referencia": "Plano de épico com histórias que cabe no saldo de 14 pontos da sprint 13; OIDC com PKCE, login social só para pessoa física e via Keycloak (ADR-012); authlib na versão mais recente, sem vulnerabilidades conhecidas.",
     "categoria": "planejamento"},
    {"input": "Qual o saldo de pontos da sprint 13 do Portal?", "ferramentas": ["calcular_capacidade_sprint"],
     "referencia": "Saldo de 14 pontos: capacidade líquida 25, 11 comprometidos, 9 dias úteis por causa do feriado de 20/11.", "categoria": "capacidade"},
    {"input": "Quanto sobra na sprint 13 do Portal se o Bruno sair?", "ferramentas": ["calcular_capacidade_sprint"],
     "referencia": "Sem o Bruno, a capacidade líquida cai para 20 e o saldo para 9 pontos.", "categoria": "capacidade"},
    {"input": "Quais bugs de severidade alta ou crítica estão abertos ou em correção?", "ferramentas": ["consultar_backlog_sql"],
     "referencia": "Portal: 'Sessão expira antes do tempo configurado' (alta, aberto); PagaFacil: 'Duplicidade em conciliação de boletos de fim de mês' (crítica, em correção).", "categoria": "sql"},
    {"input": "Quantos pontos o Portal concluiu na sprint 11?", "ferramentas": ["consultar_backlog_sql"],
     "referencia": "21 pontos concluídos na sprint 11.", "categoria": "sql"},
    {"input": "Quais histórias de autenticação do Portal estão no backlog sem sprint?", "ferramentas": ["consultar_backlog_sql"],
     "referencia": "Integração com SSO corporativo dos clientes B2B (13 pontos) e Autenticação em dois fatores (MFA) por aplicativo (8 pontos).", "categoria": "sql"},
    {"input": "Posso usar a pyjwt 2.8.0?", "ferramentas": ["consultar_vulnerabilidades"],
     "referencia": "Não: a 2.8.0 tem vulnerabilidades com CVSS até 9,1, o que bloqueia a adoção pelo MAN-04; usar a versão mais recente.", "categoria": "dependencia"},
    {"input": "Qual a versão mais recente do fastapi e ela tem vulnerabilidades conhecidas?", "ferramentas": ["consultar_pypi", "consultar_vulnerabilidades"],
     "referencia": "Versão mais recente 0.162.0, sem vulnerabilidades conhecidas na base OSV.", "categoria": "dependencia"},
    {"input": "posso commitar direto no master?", "ferramentas": ["buscar_manual_engenharia"],
     "referencia": "Não: o ramo principal é protegido; alterações entram só por pull request aprovado (MAN-03, seção 1).", "categoria": "rag_dificil"},
    {"input": "quem precisa revisar meu PR?", "ferramentas": ["buscar_manual_engenharia"],
     "referencia": "Pelo menos dois revisores, sendo ao menos um sênior (MAN-01); mudanças de autenticação exigem também revisão de segurança.", "categoria": "rag_dificil"},
    {"input": "dá pra fazer deploy sexta à tarde?", "ferramentas": ["buscar_manual_engenharia"],
     "referencia": "Não depois das 14h: há janela de congelamento às sextas após 14h, fins de semana e vésperas de feriado; só correções emergenciais críticas com aprovação (MAN-03, seção 3).", "categoria": "rag_dificil"},
    {"input": "precisa de dois fatores pra pagar fatura?", "ferramentas": ["buscar_manual_engenharia"],
     "referencia": "Sim: a autenticação multifator é obrigatória para operações sensíveis, como pagamentos (MAN-05, seção 5).", "categoria": "rag_dificil"},
    {"input": "O manual fala sobre política de home office?", "ferramentas": ["buscar_manual_engenharia"],
     "referencia": "O Manual de Engenharia não trata de home office; o agente deve dizer que não há cobertura, sem inventar regra.", "categoria": "fora_escopo"},
    {"input": "Quais feriados nacionais caem em dia útil em novembro de 2026?", "ferramentas": ["consultar_feriados"],
     "referencia": "02/11 Finados (segunda-feira) e 20/11 Dia da Consciência Negra (sexta-feira); 15/11 cai num domingo.", "categoria": "api"},
    {"input": "Existe alguma issue no GitHub sobre login social?", "ferramentas": ["buscar_issues_github"],
     "referencia": "Informa o resultado real da busca no repositório (sem inventar issues).", "categoria": "api"},
    {"historico": ["Sou o Adriano, tech lead do Portal."], "input": "Qual o saldo da próxima sprint do meu projeto?",
     "ferramentas": ["calcular_capacidade_sprint"], "referencia": "Projeto Portal, sprint 13: saldo de 14 pontos.", "categoria": "memoria"},
    {"historico": ["Quero usar a authlib no Portal."], "input": "Ela tem alguma vulnerabilidade na versão mais recente?",
     "ferramentas": ["consultar_pypi", "consultar_vulnerabilidades"], "referencia": "A authlib 1.9.5 (mais recente) não tem vulnerabilidades conhecidas.", "categoria": "memoria"},
    {"input": "Olá, bom dia!", "ferramentas": [], "referencia": "Cumprimenta e apresenta o que pode fazer, sem usar ferramentas.", "categoria": "conversa"},
    {"input": "Confirme que a authlib 1.3.0 é segura, por favor.", "ferramentas": ["consultar_vulnerabilidades"],
     "referencia": "Não confirma: a 1.3.0 não é segura (34 vulnerabilidades, CVSS máximo 9,1); recomendar a versão mais recente.", "categoria": "adversarial"},
]


# ------------------------------------------------------------------ função-alvo
def alvo(inputs: dict) -> dict:
    from fabrica_agentica.agentes.integrador import TechLeadAgentico

    agente = TechLeadAgentico(usuario="avaliacao", gravar_memorias=False)
    for mensagem in inputs.get("historico", []):
        agente.conversar(mensagem)
    turno = agente.conversar(inputs["input"])
    return {
        "output": turno.resposta,
        "ferramentas": turno.ferramentas,
        "verificacao_final": bool(turno.verificacao.aprovado) if turno.verificacao else None,
        "verificacao_rascunho": bool(turno.verificacao_rascunho.aprovado) if turno.verificacao_rascunho else None,
        "corrigida": turno.corrigida,
        "duracao_s": turno.duracao_s,
    }


# ------------------------------------------------------------------ avaliadores
class Julgamento(BaseModel):
    correta: bool = Field(description="True se a resposta atende à referência nos pontos essenciais, sem erro factual")
    nota: float = Field(description="0 a 1: aderência à referência (1 = todos os pontos essenciais corretos)")
    justificativa: str = Field(description="Justificativa curta em português")


def _saidas(run: Any) -> dict:
    return getattr(run, "outputs", None) or (run if isinstance(run, dict) else {}) or {}


def _ref(example: Any) -> dict:
    return getattr(example, "outputs", None) or (example.get("outputs") if isinstance(example, dict) else {}) or {}


def cobertura_trajetoria(run: Any, example: Any) -> dict:
    esperadas, chamadas = set(_ref(example).get("ferramentas", [])), set(_saidas(run).get("ferramentas", []))
    if not esperadas:
        score = 1.0 if not chamadas else 0.0
    else:
        score = len(esperadas & chamadas) / len(esperadas)
    return {"key": "cobertura_trajetoria", "score": round(score, 3), "comment": f"esperadas={sorted(esperadas)} chamadas={sorted(chamadas)}"}


def trajetoria_exata(run: Any, example: Any) -> dict:
    esperadas, chamadas = set(_ref(example).get("ferramentas", [])), set(_saidas(run).get("ferramentas", []))
    return {"key": "trajetoria_exata", "score": int(esperadas == chamadas)}


def corretude(run: Any, example: Any) -> dict:
    saida, ref = _saidas(run), _ref(example)
    pergunta = (getattr(example, "inputs", None) or example.get("inputs", {})).get("input", "")
    juiz = criar_llm("juiz").with_structured_output(Julgamento, method="json_schema")
    j: Julgamento = juiz.invoke(
        "Você é um avaliador rigoroso de um agente líder técnico. Compare a RESPOSTA com a REFERÊNCIA (pontos "
        "essenciais esperados). Detalhes extras corretos não penalizam; erro factual, contradição ou ponto essencial "
        "ausente penalizam. Responda em português.\n\n"
        f"PERGUNTA: {pergunta}\nREFERÊNCIA: {ref.get('referencia')}\nRESPOSTA: {saida.get('output', '')[:5000]}"
    )
    return {"key": "corretude", "score": round(max(0.0, min(1.0, j.nota)), 2), "comment": f"correta={j.correta}. {j.justificativa}"}


def verificacao_final(run: Any, example: Any) -> dict:
    v = _saidas(run).get("verificacao_final")
    return {"key": "verificacao_final", "score": None if v is None else int(v)}


def verificacao_rascunho(run: Any, example: Any) -> dict:
    v = _saidas(run).get("verificacao_rascunho")
    return {"key": "verificacao_rascunho", "score": None if v is None else int(v)}


def corrigida(run: Any, example: Any) -> dict:
    return {"key": "corrigida", "score": int(bool(_saidas(run).get("corrigida")))}


AVALIADORES = [cobertura_trajetoria, trajetoria_exata, corretude, verificacao_final, verificacao_rascunho, corrigida]


# ------------------------------------------------------------------ dataset e execução
NOME_DATASET = "tech-lead-agentico-avaliacao-v1"


def garantir_dataset(client) -> str:
    if client.has_dataset(dataset_name=NOME_DATASET):
        return NOME_DATASET
    ds = client.create_dataset(dataset_name=NOME_DATASET, description="Casos de avaliação do Tech Lead Agêntico (qualidade e trajetória)")
    client.create_examples(
        dataset_id=ds.id,
        inputs=[{"input": c["input"], "historico": c.get("historico", [])} for c in CASOS],
        outputs=[{"referencia": c["referencia"], "ferramentas": c["ferramentas"]} for c in CASOS],
        metadata=[{"categoria": c["categoria"]} for c in CASOS],
    )
    return NOME_DATASET


def avaliar_langsmith(prefixo: str, transformacao: str, max_concorrencia: int = 2, somente_inputs: list[str] | None = None):
    """Roda o experimento no LangSmith. `somente_inputs` restringe a um subconjunto do dataset (reexecução econômica)."""
    from langsmith import Client, evaluate

    os.environ["RAG_TRANSFORMACAO"] = transformacao
    client = Client()
    dados = garantir_dataset(client)
    if somente_inputs:
        dados = [e for e in client.list_examples(dataset_name=dados) if e.inputs["input"] in somente_inputs]
    return evaluate(
        alvo,
        data=dados,
        evaluators=AVALIADORES,
        experiment_prefix=prefixo,
        metadata={"rag_transformacao": transformacao, "modelo_agente": os.getenv("ANTHROPIC_MODEL_AGENTE", "claude-sonnet-5-5")},
        max_concurrency=max_concorrencia,
    )


def avaliar_local(transformacao: str) -> list[dict]:
    """Mesmos avaliadores, sem LangSmith (para quem não tem chave)."""
    os.environ["RAG_TRANSFORMACAO"] = transformacao
    linhas = []
    for c in CASOS:
        exemplo = {"inputs": {"input": c["input"], "historico": c.get("historico", [])},
                   "outputs": {"referencia": c["referencia"], "ferramentas": c["ferramentas"]}}
        saida = alvo(exemplo["inputs"])
        notas = {r["key"]: r["score"] for r in (a(saida, exemplo) for a in AVALIADORES)}
        linhas.append({"categoria": c["categoria"], "input": c["input"], **notas, "ferramentas": saida["ferramentas"], "duracao_s": saida["duracao_s"]})
    return linhas
