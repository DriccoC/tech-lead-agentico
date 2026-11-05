"""Reconhecimento de intenção, extração de entidades e fluxos de conversação.

Cada mensagem passa por um classificador (LLM auxiliar com saída estruturada) que
devolve a intenção e as entidades. As entidades alimentam um ESTADO DA SESSÃO que
persiste entre turnos ("o projeto continua sendo o Portal"). Cada intenção tem um fluxo
com entidades obrigatórias; se alguma faltar e não estiver no estado, o chatbot pergunta
antes de acionar o agente (preenchimento de lacunas / slot filling).
"""

from __future__ import annotations

from fabrica_agentica.config import criar_llm
from fabrica_agentica.esquemas import IntencaoEntidades

DESCRICAO_INTENCOES = """
- planejar_demanda: pedir para planejar/implementar algo NOVO (funcionalidade, épico, histórias) ou registrar um plano
- consultar_backlog: perguntas sobre dados do backlog e do time: sprints, capacidade, saldo, pontos, histórias, bugs,
  pessoas, issues do GitHub (ex.: "quais bugs críticos estão abertos?", "e se o Bruno sair?")
- checar_dependencia: perguntas sobre bibliotecas/pacotes, versões e vulnerabilidades
- consultar_padrao: perguntas sobre normas, processos e regras do manual de engenharia: revisão de PR, deploy,
  branches, cobertura de testes, MFA/autenticação, estimativas (ex.: "quem precisa revisar meu PR?", "pode deploy na sexta?")
- conversa_geral: cumprimentos, apresentações, agradecimentos, assuntos fora do escopo
""".strip()

# Fluxos: entidades obrigatórias por intenção e a pergunta de esclarecimento.
# Só se exige o que a tarefa realmente precisa: planejar exige o projeto; consultas ao backlog podem abranger
# todos os projetos (exigir o projeto ali bloqueava perguntas como "quais bugs críticos estão abertos?" —
# regressão encontrada na avaliação da Fase 5).
FLUXOS = {
    "planejar_demanda": {"projeto": "Para qual projeto é essa demanda: Portal, PagaFacil ou AppCampo?"},
    "consultar_backlog": {},
    "checar_dependencia": {"pacote": "Qual biblioteca (pacote) você quer que eu verifique?"},
    "consultar_padrao": {},
    "conversa_geral": {},
}
CAMPOS_ESTADO = ("projeto", "sprint", "pacote", "versao", "prioridade", "pessoa")


def reconhecer(mensagem: str, estado: dict | None = None, ultima_resposta: str = "") -> IntencaoEntidades:
    contexto = f"Entidades já conhecidas na sessão: {estado}" if estado else "Sem contexto anterior."
    if ultima_resposta:
        contexto += f"\nÚltima resposta do assistente (para resolver referências): {ultima_resposta[:1200]}"
    classificador = criar_llm("auxiliar").with_structured_output(IntencaoEntidades, method="json_schema")
    return classificador.invoke(
        "Classifique a intenção da MENSAGEM e extraia as entidades citadas nela ou referidas por ela. Resolva "
        "referências pelo contexto (ex.: 'a biblioteca que você sugeriu' -> o pacote sugerido na última resposta). "
        "Não preencha entidades que a mensagem não cita nem referencia. Intenções:\n"
        f"{DESCRICAO_INTENCOES}\n\n{contexto}\n\nMENSAGEM: {mensagem}"
    )


def entidades_da_trajetoria(passos: list[dict]) -> dict:
    """Entidades que o agente usou nas ferramentas (ex.: o pacote que ele consultou e sugeriu)."""
    achadas: dict = {}
    for passo in passos:
        args = passo.get("argumentos") or {}
        if not isinstance(args, dict):
            continue
        if args.get("projeto"):
            achadas["projeto"] = args["projeto"]
        if args.get("numero_sprint"):
            achadas["sprint"] = args["numero_sprint"]
        if args.get("pacote"):
            achadas["pacote"] = args["pacote"]
    return achadas


def atualizar_estado(estado: dict, reconhecido: IntencaoEntidades) -> dict:
    """Mescla as entidades novas no estado da sessão (as novas prevalecem)."""
    novo = dict(estado)
    for campo in CAMPOS_ESTADO:
        valor = getattr(reconhecido, campo)
        if valor not in (None, ""):
            novo[campo] = valor
    return novo


def lacunas(intencao: str, estado: dict) -> list[str]:
    """Perguntas de esclarecimento para entidades obrigatórias ausentes."""
    return [pergunta for campo, pergunta in FLUXOS.get(intencao, {}).items() if not estado.get(campo)]
