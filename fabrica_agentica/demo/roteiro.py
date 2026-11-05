"""Regras de decisão do modelo de demonstração (palavras-chave, sem IA).

As funções aqui imitam o que um LLM faria em cada protocolo. Os textos finais são
montados a partir das SAÍDAS DAS FERRAMENTAS, então os números exibidos no modo demo
vêm sempre das ferramentas reais (cálculo, SQL, FAISS, fixtures das APIs).
"""

from __future__ import annotations

import json
import re
import typing
import unicodedata
from typing import Any, Callable, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from pydantic import BaseModel

PROJETOS = {"portal": "Portal", "pagafacil": "PagaFacil", "paga facil": "PagaFacil", "appcampo": "AppCampo", "app campo": "AppCampo"}
PESSOAS = ["Ana", "Bruno", "Carla", "Diego", "Eduarda", "Felipe", "Gabriela", "Henrique"]
PACOTES = ["authlib", "fastapi", "pyjwt", "requests", "python-jose", "django", "flask", "pydantic", "sqlalchemy"]

# Reescrita de consulta "à moda do LLM": termos coloquiais -> vocabulário das normas.
REESCRITAS = [
    (("main", "master", "direto", "commit", "subir"), "ramo principal protegido envio direto solicitação de incorporação pull request"),
    (("sexta", "deploy", "produção", "producao", "implantar", "subir"), "janela de congelamento de mudanças implantação em produção sexta-feira"),
    (("revis", "pr", "pull request", "aprova"), "revisão de código aprovada por dois revisores sênior Definição de Pronto"),
    (("cobertura", "teste"), "cobertura de testes automatizados mínimo 80% Definição de Pronto"),
    (("google", "login", "social", "oauth", "autentic", "sso"), "provedores de identidade federada login social OpenID Connect Keycloak ADR-012"),
    (("cve", "vulnerab", "segur", "lib", "biblioteca", "dependen"), "vulnerabilidade CVSS critérios de admissão de componentes MAN-04"),
    (("token", "sessão", "sessao", "senha", "tentativa"), "tokens de acesso validade sessões bloqueio após tentativas"),
    (("ponto", "estimat", "capacidade", "sprint"), "estimativa Fibonacci capacidade da sprint decomposição de histórias"),
]


def normalizar(texto: str) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


# ============================================================== extração de entidades
def extrair_projeto(texto: str) -> Optional[str]:
    t = normalizar(texto)
    for chave, nome in PROJETOS.items():
        if chave in t:
            return nome
    return None


def extrair_sprint(texto: str) -> Optional[int]:
    m = re.search(r"sprint\s*(\d+)", normalizar(texto))
    return int(m.group(1)) if m else None


def extrair_pacote(texto: str) -> Optional[str]:
    t = normalizar(texto)
    for p in PACOTES:
        if re.search(rf"\b{re.escape(p)}\b", t):
            return p
    if any(k in t for k in ("google", "login social", "oauth", "oidc")):
        return "authlib"  # biblioteca homologada no MAN-05
    return None


def extrair_versao(texto: str) -> Optional[str]:
    m = re.search(r"\b(\d+\.\d+(?:\.\d+)?)\b", texto)
    return m.group(1) if m else None


def extrair_pessoas(texto: str) -> list[str]:
    t = normalizar(texto)
    return [p for p in PESSOAS if normalizar(p) in t.split() or f" {normalizar(p)}" in f" {t}"]


def classificar_intencao(texto: str) -> str:
    t = normalizar(texto)
    if any(k in t for k in ("registr", "cadastr", "abra as issues", "abrir issues", "pode gravar", "confirm")):
        return "registrar"
    if any(k in t for k in ("quero ", "precisamos", "planej", "implementar", "criar ", "adicionar", "nova funcionalidade")):
        return "planejar_demanda"
    if any(k in t for k in ("vulnerab", "cve", "versao", "atualizad", "seguro usar", "lib ", "biblioteca")) or extrair_versao(texto):
        return "checar_dependencia"
    if any(k in t for k in ("capacidade", "saldo", "sobra", "cabe", "quantos pontos", "historias", "bugs", "backlog", "quem esta", "sprint", "tirar", "tirarmos", "sem o", "sem a")):
        return "consultar_backlog"
    if any(k in t for k in ("posso", "pode ", "norma", "padrao", "regra", "politica", "manual", "revisar", "cobertura", "deploy", "main", "master")):
        return "consultar_padrao"
    return "conversa_geral"


def reescrever_consulta(texto: str) -> str:
    t = normalizar(texto)
    partes = [alvo for chaves, alvo in REESCRITAS if any(c in t for c in chaves)]
    return " ".join(dict.fromkeys(partes)) or texto


# ============================================================== saída estruturada
ESTRUTURADORES: dict[str, Callable[[str], dict]] = {}


def registrar_estruturador(nome_esquema: str):
    """Decorador para módulos registrarem a heurística demo de um esquema Pydantic."""

    def decorar(funcao: Callable[[str], dict]):
        ESTRUTURADORES[nome_esquema] = funcao
        return funcao

    return decorar


def _valor_padrao(anotacao: Any) -> Any:
    origem = typing.get_origin(anotacao)
    if origem is typing.Literal:
        return typing.get_args(anotacao)[0]
    if origem in (typing.Union, getattr(__import__("types"), "UnionType", None)):
        return None
    if origem is list or anotacao is list:
        return []
    if anotacao is bool:
        return True
    if anotacao in (int, float):
        return 0
    if isinstance(anotacao, type) and issubclass(anotacao, BaseModel):
        return _instancia_padrao(anotacao).model_dump()
    return ""


def _instancia_padrao(esquema: type[BaseModel]) -> BaseModel:
    dados = {}
    for nome, campo in esquema.model_fields.items():
        dados[nome] = campo.default if not campo.is_required() else _valor_padrao(campo.annotation)
    return esquema.model_validate(dados)


def estruturar(esquema: Any, texto: str) -> Any:
    """Devolve uma instância do esquema preenchida por heurística."""
    if isinstance(esquema, dict):  # esquema JSON puro: devolve dict vazio
        return {}
    funcao = ESTRUTURADORES.get(esquema.__name__)
    if funcao is None:
        return _instancia_padrao(esquema)
    return esquema.model_validate(funcao(texto))


def esquema_em_instrucoes(prompt: str):
    """Detecta instruções de PydanticOutputParser e devolve o esquema correspondente."""
    if "JSON instance that conforms to the JSON schema" not in prompt and "output should be formatted as a JSON" not in prompt:
        return None
    from fabrica_agentica import esquemas

    for nome in ("PlanoTrabalho", "AnaliseDemanda", "IntencaoEntidades"):
        classe = getattr(esquemas, nome)
        if all(f'"{campo}"' in prompt for campo in list(classe.model_fields)[:3]):
            return classe
    return None


def ultimo_texto_usuario(prompt: str) -> str:
    for marcador in ("DEMANDA:", "MENSAGEM:", "Human:", "Question:"):
        if marcador in prompt:
            return prompt.rsplit(marcador, 1)[1].strip().split("\n\n")[0]
    return prompt.strip().splitlines()[-1] if prompt.strip() else ""


@registrar_estruturador("AnaliseDemanda")
def _analise(texto: str) -> dict:
    texto = ultimo_texto_usuario(texto)
    t = normalizar(texto)
    tipo = "correcao" if any(k in t for k in ("bug", "erro", "falha", "corrig")) else (
        "duvida" if t.strip().endswith("?") else "nova_funcionalidade")
    componentes = [c for c, ks in {"backend": ("api", "login", "pagamento", "backend", "integra"), "front-end": ("tela", "login", "botao", "pagina", "portal"),
                   "banco de dados": ("dados", "cadastro", "historico"), "seguranca": ("login", "senha", "token", "google")}.items() if any(k in t for k in ks)]
    return {
        "resumo": f"Demanda: {texto.strip()[:140]}",
        "tipo": tipo,
        "projeto": extrair_projeto(texto),
        "componentes_afetados": componentes or ["backend"],
        "complexidade": "alta" if len(componentes) >= 3 else ("media" if len(componentes) == 2 else "baixa"),
        "riscos": ["Impacto em autenticação exige revisão de segurança (MAN-05)"] if "seguranca" in componentes else ["Escopo ainda pouco detalhado"],
        "perguntas_em_aberto": ["Qual o prazo esperado?", "Há restrição de orçamento ou de time?"],
        "proximos_passos": ["Validar escopo com o responsável de produto", "Decompor em histórias com critérios Gherkin"],
    }


@registrar_estruturador("IntencaoEntidades")
def _intencao(texto: str) -> dict:
    texto = ultimo_texto_usuario(texto)
    intencao = classificar_intencao(texto)
    pessoas = extrair_pessoas(texto)
    t = normalizar(texto)
    prioridade = next((p for p in ("alta", "media", "baixa") if f"prioridade {p}" in t or f"{p} prioridade" in t), None)
    return {
        "intencao": intencao if intencao != "registrar" else "planejar_demanda",
        "projeto": extrair_projeto(texto),
        "sprint": extrair_sprint(texto),
        "pacote": extrair_pacote(texto) if intencao in ("checar_dependencia", "planejar_demanda") else None,
        "versao": extrair_versao(texto),
        "prioridade": prioridade,
        "pessoa": pessoas[0] if pessoas else None,
    }


@registrar_estruturador("PlanoTrabalho")
def _plano(texto: str) -> dict:
    texto = ultimo_texto_usuario(texto)
    t = normalizar(texto)
    if any(k in t for k in ("google", "login social", "oauth")):
        return {
            "epico": "Login com Google no Portal",
            "objetivo": "Permitir que clientes pessoa física entrem com a conta Google, reduzindo atrito no acesso.",
            "historias": [
                {"titulo": "Como administrador de identidade, quero configurar o Google como provedor federado no Keycloak, para centralizar a autenticação (ADR-012)",
                 "criterios_aceite": ["Dado o Keycloak de homologação, quando o provedor Google for configurado, então o fluxo OIDC com PKCE deve concluir com sucesso"],
                 "pontos": 3, "tarefas": ["Registrar aplicação no Google Cloud", "Configurar provedor no Keycloak", "Documentar ADR de configuração"]},
                {"titulo": "Como cliente pessoa física, quero entrar no Portal com minha conta Google, para acessar sem criar senha",
                 "criterios_aceite": ["Dado um cliente com e-mail verificado no Google, quando clicar em 'Entrar com Google', então deve acessar a área logada",
                                      "Dado um cliente corporativo (B2B), quando tentar o login social, então deve ser direcionado à federação corporativa"],
                 "pontos": 5, "tarefas": ["Botão 'Entrar com Google' no front-end", "Integração OIDC com authlib", "Testes de contrato do callback"]},
                {"titulo": "Como cliente, quero vincular minha conta Google à conta existente, para não duplicar cadastro",
                 "criterios_aceite": ["Dado um e-mail já cadastrado, quando entrar com Google pela primeira vez, então deve confirmar a vinculação por e-mail"],
                 "pontos": 3, "tarefas": ["Fluxo de vinculação", "E-mail de confirmação", "Testes automatizados (cobertura >= 80%)"]},
                {"titulo": "Como time de segurança, quero revisar a integração de login social, para cumprir o MAN-05",
                 "criterios_aceite": ["Dado o pull request da integração, quando a revisão de segurança for concluída, então não deve haver vulnerabilidade alta ou crítica"],
                 "pontos": 2, "tarefas": ["Revisão de segurança", "Análise de dependências (OSV)"]},
            ],
            "riscos": ["Depende do Keycloak corporativo (ADR-012)", "Somente pessoa física pode usar login social (MAN-05 §2)"],
        }
    return {
        "epico": f"Épico: {texto.strip()[:60]}",
        "objetivo": "Entregar a demanda em incrementos pequenos e testáveis.",
        "historias": [
            {"titulo": "Como usuário, quero a funcionalidade principal da demanda, para obter o benefício descrito",
             "criterios_aceite": ["Dado o cenário principal, quando o usuário executar a ação, então o resultado esperado deve ser exibido"], "pontos": 5,
             "tarefas": ["Implementar backend", "Implementar front-end", "Testes automatizados"]},
            {"titulo": "Como time de qualidade, quero cenários de teste da demanda, para garantir a Definição de Pronto",
             "criterios_aceite": ["Dado o incremento em homologação, quando os testes rodarem, então a cobertura deve ser de pelo menos 80%"], "pontos": 3,
             "tarefas": ["Escrever testes", "Teste exploratório"]},
        ],
        "riscos": ["Escopo precisa ser validado com o responsável de produto"],
    }


# ============================================================== RouterChain
def rotear(prompt: str) -> str:
    candidatos = re.findall(r"^([a-z_]+): ", prompt.split("<< CANDIDATE PROMPTS >>")[-1].split("<< INPUT >>")[0], flags=re.M)
    entrada = prompt.split("<< INPUT >>")[-1].split("<< OUTPUT")[0].strip()
    mapa = {"planejar_demanda": "planejamento", "consultar_backlog": "planejamento", "checar_dependencia": "seguranca",
            "consultar_padrao": "consulta_tecnica", "registrar": "planejamento", "conversa_geral": "DEFAULT"}
    destino = mapa.get(classificar_intencao(entrada), "DEFAULT")
    if destino != "DEFAULT" and candidatos and destino not in candidatos:
        destino = "DEFAULT"
    return "```json\n" + json.dumps({"destination": destino, "next_inputs": entrada}, ensure_ascii=False) + "\n```"


# ============================================================== ReAct (texto)
def passo_react(prompt: str) -> str:
    nomes = re.findall(r"should be one of \[(.*?)\]", prompt)
    ferramentas = [n.strip() for n in nomes[-1].split(",")] if nomes else []
    pergunta = prompt.rsplit("Question:", 1)[-1]
    observacoes = re.findall(r"Observation:(.*?)(?:\nThought:|$)", pergunta, flags=re.S)
    q = pergunta.split("\n")[0].strip()
    intencao = classificar_intencao(q)
    plano: list[tuple[str, str]] = []
    if intencao == "checar_dependencia":
        pacote = extrair_pacote(q) or "authlib"
        plano = [("consultar_pypi", pacote), ("consultar_vulnerabilidades", f"{pacote}=={extrair_versao(q) or 'mais_recente'}")]
    elif intencao in ("consultar_backlog", "planejar_demanda"):
        plano = [("calcular_capacidade_sprint", extrair_projeto(q) or "Portal")]
        if intencao == "planejar_demanda":
            plano.append(("buscar_manual_engenharia", reescrever_consulta(q)))
    elif intencao == "consultar_padrao":
        plano = [("buscar_manual_engenharia", reescrever_consulta(q))]
    plano = [p for p in plano if p[0] in ferramentas]
    if len(observacoes) < len(plano):
        nome, entrada = plano[len(observacoes)]
        if nome == "consultar_vulnerabilidades" and "mais_recente" in entrada and observacoes:
            achado = re.search(r'"versao_mais_recente": "([^"]+)"', observacoes[-1])
            entrada = entrada.replace("mais_recente", achado.group(1) if achado else "0")
        pensamento = "Preciso consultar uma ferramenta para não responder de memória." if not observacoes else "Ainda falta uma informação; vou usar outra ferramenta."
        return f"Thought: {pensamento}\nAction: {nome}\nAction Input: {entrada}"
    resumo = " | ".join(o.strip()[:220] for o in observacoes) or "Nenhuma ferramenta foi necessária."
    return f"Thought: Já tenho as informações necessárias.\nFinal Answer: [modo demonstração] Com base nas ferramentas: {resumo}"


# ============================================================== tool calling
def _contador():
    _contador.n = getattr(_contador, "n", 0) + 1
    return f"demo_{_contador.n}"


def _chamada(nome: str, args: dict) -> dict:
    return {"name": nome, "args": args, "id": _contador(), "type": "tool_call"}


def _json_ou_texto(conteudo: str) -> Any:
    try:
        return json.loads(conteudo)
    except (TypeError, ValueError):
        return conteudo


def passo_ferramentas(messages: list[BaseMessage], nomes: list[str]) -> AIMessage:
    indice_humano = max((i for i, m in enumerate(messages) if isinstance(m, HumanMessage)), default=0)
    humano = messages[indice_humano].content if messages else ""
    humano = humano if isinstance(humano, str) else " ".join(b.get("text", "") for b in humano if isinstance(b, dict))
    nomes_por_id = {tc["id"]: tc["name"] for m in messages if isinstance(m, AIMessage) for tc in (m.tool_calls or [])}
    for m in messages:  # o AgentExecutor clássico cria ToolMessage sem `name`
        if isinstance(m, ToolMessage) and not m.name:
            m.name = nomes_por_id.get(m.tool_call_id)
    resultados = {m.name: _json_ou_texto(m.content) for m in messages[indice_humano:] if isinstance(m, ToolMessage)}
    anteriores = [m for m in messages[:indice_humano] if isinstance(m, ToolMessage)]
    intencao = classificar_intencao(humano)
    projeto = extrair_projeto(humano) or _projeto_do_historico(messages) or "Portal"
    pacote = extrair_pacote(humano)
    pessoas = extrair_pessoas(humano)

    chamadas: list[dict] = []
    if intencao == "planejar_demanda":
        if not resultados:
            chamadas = [
                _chamada("calcular_capacidade_sprint", {"projeto": projeto}),
                _chamada("buscar_manual_engenharia", {"consulta_otimizada": reescrever_consulta(humano)}),
                _chamada("buscar_issues_github", {"termo": (pacote and "google" in normalizar(humano) and "google") or (pacote or humano.split()[-1])}),
            ]
            if pacote:
                chamadas.append(_chamada("consultar_pypi", {"pacote": pacote}))
        elif "consultar_pypi" in resultados and "consultar_vulnerabilidades" not in resultados:
            chamadas = [_chamada("consultar_vulnerabilidades", {"pacote": pacote, "versao": resultados["consultar_pypi"].get("versao_mais_recente", "0")})]
        elif "decompor_demanda" not in resultados:
            cap = resultados.get("calcular_capacidade_sprint", {})
            contexto = f"Saldo da sprint: {cap.get('saldo_disponivel', '?')} pontos. Normas: {_fontes(resultados.get('buscar_manual_engenharia'))}."
            chamadas = [_chamada("decompor_demanda", {"demanda": humano, "contexto": contexto})]
    elif intencao == "registrar":
        acao = "registrar_no_backlog" if "registrar_no_backlog" in nomes else "propor_registro_backlog"
        if acao not in resultados:
            plano = (resultados.get("decompor_demanda") or {}).get("plano") or _ultimo_plano(anteriores)
            if plano:
                chamadas = [_chamada(acao, {"projeto": projeto, "numero_sprint": _ultima_sprint(anteriores) or 13, "plano": plano, "abrir_issues": True})]
            elif "decompor_demanda" not in resultados:
                demanda = next((_texto(m) for m in reversed(messages[:indice_humano]) if isinstance(m, HumanMessage)
                                and classificar_intencao(_texto(m)) == "planejar_demanda"), humano)
                chamadas = [_chamada("decompor_demanda", {"demanda": demanda, "contexto": "registro solicitado pelo usuário"})]
    elif intencao == "checar_dependencia":
        versao = extrair_versao(humano)
        if not resultados and pacote:
            chamadas = [_chamada("consultar_pypi", {"pacote": pacote})]
        elif "consultar_pypi" in resultados and "consultar_vulnerabilidades" not in resultados:
            recente = resultados["consultar_pypi"].get("versao_mais_recente", "0")
            chamadas = [_chamada("consultar_vulnerabilidades", {"pacote": pacote, "versao": versao or recente})]
            if versao:
                chamadas.append(_chamada("comparar_versoes", {"versao_atual": versao, "versao_mais_recente": recente}))
        elif "consultar_vulnerabilidades" in resultados and "classificar_cvss" not in resultados:
            maior = resultados["consultar_vulnerabilidades"].get("maior_cvss") or 0
            if maior:
                chamadas = [_chamada("classificar_cvss", {"pontuacao": maior})]
    elif intencao == "consultar_backlog" and not resultados:
        t = normalizar(humano)
        if any(k in t for k in ("capacidade", "saldo", "sobra", "cabe", "quantos pontos", "tirar", "tirarmos", "sem o", "sem a")):
            chamadas = [_chamada("calcular_capacidade_sprint", {"projeto": projeto, "numero_sprint": extrair_sprint(humano), "remover_integrantes": pessoas})]
        else:
            chamadas = [_chamada("consultar_backlog_sql", {"consulta_sql": _sql_modelo(humano, projeto)})]
    elif intencao == "consultar_padrao" and not resultados:
        chamadas = [_chamada("buscar_manual_engenharia", {"consulta_otimizada": reescrever_consulta(humano)})]

    chamadas = [c for c in chamadas if c["name"] in nomes]
    if chamadas:
        return AIMessage(content="", tool_calls=chamadas)
    return AIMessage(content=compor_resposta(humano, resultados, messages))


def _projeto_do_historico(messages: list[BaseMessage]) -> Optional[str]:
    for m in reversed(messages):
        if isinstance(m, HumanMessage) and extrair_projeto(_texto(m)):
            return extrair_projeto(_texto(m))
    return None


def _texto(m: BaseMessage) -> str:
    return m.content if isinstance(m.content, str) else " ".join(b.get("text", "") for b in m.content if isinstance(b, dict))


def _ultimo_plano(mensagens: list[BaseMessage]) -> Optional[dict]:
    for m in reversed(mensagens):
        if isinstance(m, ToolMessage) and m.name == "decompor_demanda":
            return _json_ou_texto(m.content).get("plano")
    return None


def _ultima_sprint(mensagens: list[BaseMessage]) -> Optional[int]:
    for m in reversed(mensagens):
        if isinstance(m, ToolMessage) and m.name == "calcular_capacidade_sprint":
            return _json_ou_texto(m.content).get("sprint")
    return None


def _fontes(resultado: Any) -> str:
    if not isinstance(resultado, dict):
        return "nenhuma"
    return ", ".join(f"{r['doc_id']} ({r['secao']})" for r in resultado.get("resultados", [])[:2])


def _sql_modelo(texto: str, projeto: str) -> str:
    t = normalizar(texto)
    if "bug" in t:
        return f"SELECT b.titulo, b.severidade, b.status FROM bugs b JOIN projetos p USING (projeto_id) WHERE p.nome = '{projeto}' AND b.status <> 'resolvido'"
    sprint = extrair_sprint(texto)
    if sprint:
        return ("SELECT h.titulo, h.pontos, h.status FROM historias h JOIN sprints s ON h.sprint_id = s.sprint_id "
                f"JOIN projetos p ON s.projeto_id = p.projeto_id WHERE p.nome = '{projeto}' AND s.numero = {sprint}")
    return f"SELECT h.titulo, h.pontos, h.prioridade FROM historias h JOIN projetos p USING (projeto_id) WHERE p.nome = '{projeto}' AND h.sprint_id IS NULL"


def compor_resposta(humano: str, resultados: dict, messages: list[BaseMessage]) -> str:
    """Monta a resposta final a partir das saídas das ferramentas (sem inventar números)."""
    linhas: list[str] = []
    cap = resultados.get("calcular_capacidade_sprint")
    if isinstance(cap, dict) and "saldo_disponivel" in cap:
        feriados = ", ".join(f"{f['date']} ({f['name']})" for f in cap.get("feriados_em_dia_util", [])) or "nenhum"
        removidos = f" Simulação sem: {', '.join(cap['integrantes_removidos_na_simulacao'])}." if cap.get("integrantes_removidos_na_simulacao") else ""
        linhas.append(
            f"A sprint {cap['sprint']} do {cap['projeto']} tem {cap['dias_uteis']} dias úteis (feriado em dia útil: {feriados}). "
            f"A capacidade líquida é de {cap['capacidade_liquida']} pontos, com {cap['pontos_comprometidos']} pontos já comprometidos, "
            f"restando {cap['saldo_disponivel']} pontos disponíveis.{removidos}"
        )
    pypi = resultados.get("consultar_pypi")
    if isinstance(pypi, dict) and pypi.get("versao_mais_recente"):
        linhas.append(f"A versão estável mais recente de {pypi['pacote']} no PyPI é a {pypi['versao_mais_recente']}.")
    osv = resultados.get("consultar_vulnerabilidades")
    if isinstance(osv, dict) and "total" in osv:
        if osv["total"]:
            linhas.append(f"A versão {osv['versao']} de {osv['pacote']} tem {osv['total']} vulnerabilidades conhecidas na base OSV; a maior pontuação CVSS é {osv.get('maior_cvss')}.")
        else:
            linhas.append(f"A versão {osv['versao']} de {osv['pacote']} não tem vulnerabilidades conhecidas na base OSV.")
    cvss = resultados.get("classificar_cvss")
    if isinstance(cvss, dict):
        linhas.append(f"Pela faixa do MAN-04, CVSS {cvss['cvss']} é severidade {cvss['severidade']}" + (" e bloqueia a adoção." if cvss["bloqueia_adocao"] else "."))
    comp = resultados.get("comparar_versoes")
    if isinstance(comp, dict):
        linhas.append(f"A versão {comp['versao_atual']} está {comp['situacao']} em relação à {comp['versao_mais_recente']} (" + ("conforme" if comp["conforme_MAN_04"] else "não conforme") + " o MAN-04).")
    manual = resultados.get("buscar_manual_engenharia")
    if isinstance(manual, dict) and manual.get("resultados"):
        melhor = manual["resultados"][0]
        trecho = re.sub(r"\s+", " ", melhor["trecho"].split("\n", 1)[-1])[:260]
        linhas.append(f"Segundo o {melhor['doc_id']} ({melhor['secao']}, {melhor['chunk_id']}): {trecho}")
        if manual.get("aviso"):
            linhas.append(manual["aviso"])
    issues = resultados.get("buscar_issues_github")
    if isinstance(issues, dict) and issues.get("issues"):
        linhas.append("Issues relacionadas no GitHub: " + "; ".join(f"#{i['numero']} {i['titulo']} ({i['estado']})" for i in issues["issues"]) + ".")
    plano = resultados.get("decompor_demanda")
    if isinstance(plano, dict) and plano.get("plano"):
        p = plano["plano"]
        linhas.append(f"Proposta de épico '{p['epico']}' com {len(p['historias'])} histórias, total de {plano['total_pontos']} pontos:")
        linhas += [f"  - {h['titulo']} ({h['pontos']} pts)" for h in p["historias"]]
        if isinstance(cap, dict) and "saldo_disponivel" in cap:
            cabe = plano["total_pontos"] <= cap["saldo_disponivel"]
            linhas.append(f"O total de {plano['total_pontos']} pontos " + ("cabe" if cabe else "não cabe") + f" no saldo de {cap['saldo_disponivel']} pontos da sprint.")
        linhas.append("Se quiser, posso registrar essas histórias no backlog e abrir as issues (pedirei sua confirmação).")
    sqlr = resultados.get("consultar_backlog_sql")
    if isinstance(sqlr, dict):
        if sqlr.get("ok"):
            linhas.append(f"A consulta retornou {sqlr['total']} registros: " + "; ".join(", ".join(str(v) for v in l.values()) for l in sqlr["linhas"][:8]) + ".")
        else:
            linhas.append(sqlr.get("erro", "Erro na consulta."))
    reg = resultados.get("propor_registro_backlog") or resultados.get("registrar_no_backlog")
    if isinstance(reg, dict) and reg.get("pendencia_id"):
        linhas.append(f"Registro proposto (pendência {reg['pendencia_id']}): {len(reg['historias'])} histórias, {reg['total_pontos']} pontos. Confirme na interface para gravar e abrir as issues.")
    elif isinstance(reg, dict) and reg.get("historias_criadas"):
        linhas.append(f"Registro aprovado e executado: {len(reg['historias_criadas'])} histórias gravadas no backlog e {len(reg.get('issues', []))} issues abertas.")
    elif isinstance(reg, str) and reg:
        linhas.append(f"Registro não executado: {reg[:200]}")
    if not linhas:
        return resposta_conversa(messages)
    return "[modo demonstração] " + "\n".join(linhas)


def resposta_conversa(messages: list[BaseMessage]) -> str:
    humanos = [_texto(m) for m in messages if isinstance(m, HumanMessage)]
    atual = humanos[-1] if humanos else ""
    t = normalizar(atual)
    if t.startswith("atualize o resumo") or t.startswith("resuma esta sessao"):
        falas = re.findall(r"Human: (.+)", atual)
        inicio = f"Em {__import__('datetime').date.today():%d/%m/%Y}, sessão" if t.startswith("resuma esta") else "Sessão"
        return f"{inicio} sobre: " + "; ".join(f.strip()[:80] for f in falas[-6:]) + "."
    if t.startswith("resuma"):
        corpo = atual.split(":", 1)[-1].split("Resumo:")[0].strip()
        return f"[modo demonstração] {corpo[:1].upper()}{corpo[1:]}"
    if "meu nome" in t and "?" in atual:
        for anterior in reversed(humanos[:-1]):
            m = re.search(r"meu nome (?:e|eh|é)\s+([A-Za-zÀ-ú]+)", anterior, flags=re.I)
            if m:
                return f"[modo demonstração] Seu nome é {m.group(1)}."
        return "[modo demonstração] Você ainda não me disse seu nome."
    m = re.search(r"meu nome (?:e|eh|é)\s+([A-Za-zÀ-ú]+)", atual, flags=re.I)
    if m:
        return f"[modo demonstração] Prazer, {m.group(1)}! Sou o Tech Lead Agêntico. Em que demanda posso ajudar?"
    if any(k in t for k in ("ola", "oi", "bom dia", "boa tarde", "boa noite")):
        return "[modo demonstração] Olá! Sou o Tech Lead Agêntico da NovaForja. Posso planejar demandas, consultar o backlog, checar bibliotecas e normas."
    return f"[modo demonstração] Entendi: \"{atual[:120]}\". Posso planejar uma demanda, consultar o backlog, checar uma biblioteca ou uma norma do manual."
