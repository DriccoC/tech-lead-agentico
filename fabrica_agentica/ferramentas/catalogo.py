"""Catálogo de ferramentas do Tech Lead Agêntico (formato LangChain `@tool`).

Cada ferramenta tem os três pilares vistos na Aula 6: NOME, DESCRIÇÃO/ESQUEMA (a
interface que o LLM lê para decidir quando e como chamar) e LÓGICA CENTRAL.

| Ferramenta                  | Tipo             |
|-----------------------------|------------------|
| calcular_capacidade_sprint  | hardcoded (+ SQL e API de feriados para os insumos) |
| comparar_versoes            | hardcoded        |
| classificar_cvss            | hardcoded        |
| consultar_feriados          | API externa      |
| consultar_pypi              | API externa      |
| consultar_vulnerabilidades  | API externa      |
| buscar_issues_github        | API externa      |
| consultar_backlog_sql       | text-to-query    |
| buscar_manual_engenharia    | RAG (FAISS existente) |
| decompor_demanda            | semântica        |
| resumir_texto_tecnico       | semântica        |
| propor_registro_backlog     | ação (pendente de aprovação humana) |
"""

from __future__ import annotations

import json
import os
from datetime import date
from typing import Optional

from langchain_core.tools import tool
from pydantic import BaseModel, Field

from fabrica_agentica.config import criar_llm, texto_de
from fabrica_agentica.esquemas import PlanoTrabalho
from fabrica_agentica.ferramentas import acoes, apis, hardcoded, rag, sql


def _json(dados) -> str:
    return json.dumps(dados, ensure_ascii=False, default=str)


# ============================================================== hardcoded
class ArgsCapacidade(BaseModel):
    projeto: str = Field(description="Nome do projeto: Portal, PagaFacil ou AppCampo")
    numero_sprint: Optional[int] = Field(default=None, description="Número da sprint; omita para usar a próxima sprint planejada")
    remover_integrantes: list[str] = Field(default_factory=list, description="Simulação: nomes de integrantes a retirar da sprint")


@tool(args_schema=ArgsCapacidade)
def calcular_capacidade_sprint(projeto: str, numero_sprint: Optional[int] = None, remover_integrantes: Optional[list[str]] = None) -> str:
    """Calcula a capacidade de pontos de uma sprint pela fórmula do MAN-06 (dias úteis sem feriados,
    ausências, fator de foco, reserva de 20%) e o saldo disponível para novas histórias.
    Use SEMPRE esta ferramenta para capacidade; nunca calcule de cabeça."""
    remover = {n.lower() for n in (remover_integrantes or [])}
    with sql.conexao_leitura() as conn:
        if numero_sprint is None:
            linha = conn.execute(
                "SELECT s.* FROM sprints s JOIN projetos p USING (projeto_id) WHERE lower(p.nome)=lower(?) AND s.status='planejada' ORDER BY s.numero LIMIT 1",
                (projeto,),
            ).fetchone()
        else:
            linha = conn.execute(
                "SELECT s.* FROM sprints s JOIN projetos p USING (projeto_id) WHERE lower(p.nome)=lower(?) AND s.numero=?",
                (projeto, numero_sprint),
            ).fetchone()
        if linha is None:
            return _json({"erro": f"Sprint não encontrada para o projeto {projeto}."})
        integrantes = [
            hardcoded.Integrante(r["nome"], r["fator_foco"], r["dias_ausencia"])
            for r in conn.execute(
                "SELECT d.nome, a.fator_foco, a.dias_ausencia FROM alocacoes a JOIN desenvolvedores d USING (dev_id) WHERE a.sprint_id=?",
                (linha["sprint_id"],),
            )
            if not any(n in r["nome"].lower() for n in remover)
        ]
        comprometidos = conn.execute("SELECT COALESCE(SUM(pontos),0) FROM historias WHERE sprint_id=?", (linha["sprint_id"],)).fetchone()[0]

    inicio, fim = date.fromisoformat(linha["inicio"]), date.fromisoformat(linha["fim"])
    try:
        feriados_api = apis.feriados_nacionais(inicio.year)
        fonte_feriados = "BrasilAPI" if not apis.apis_offline() else "BrasilAPI (resposta gravada)"
    except apis.ErroAPIExterna as erro:
        feriados_api, fonte_feriados = [], f"indisponível ({erro}); feriados não descontados"
    feriados = {date.fromisoformat(f["date"]) for f in feriados_api}
    uteis = hardcoded.dias_uteis(inicio, fim, feriados)
    feriados_no_periodo = [f for f in feriados_api if inicio <= date.fromisoformat(f["date"]) <= fim and date.fromisoformat(f["date"]).weekday() < 5]

    resultado = hardcoded.calcular_capacidade(integrantes, len(uteis), int(comprometidos))
    resultado.update(
        {
            "projeto": projeto,
            "sprint": linha["numero"],
            "periodo": f"{linha['inicio']} a {linha['fim']}",
            "feriados_em_dia_util": feriados_no_periodo,
            "fonte_feriados": fonte_feriados,
            "integrantes_removidos_na_simulacao": sorted(remover),
            "regra": "MAN-06 §3",
        }
    )
    return _json(resultado)


@tool
def comparar_versoes(versao_atual: str, versao_mais_recente: str) -> str:
    """Compara uma versão em uso com a mais recente (versionamento semântico) e diz se está conforme
    a regra de defasagem do MAN-04 (no máximo uma versão MINOR atrás)."""
    return _json(hardcoded.comparar_versoes(versao_atual, versao_mais_recente))


@tool
def classificar_cvss(pontuacao: float) -> str:
    """Classifica uma pontuação CVSS v3 (0 a 10) na faixa de severidade do MAN-04 e diz se a
    vulnerabilidade bloqueia a adoção do componente (CVSS >= 7,0)."""
    return _json(hardcoded.classificar_cvss(pontuacao))


# ============================================================== APIs externas
@tool
def consultar_feriados(ano: int) -> str:
    """Lista os feriados nacionais brasileiros de um ano (API pública BrasilAPI)."""
    try:
        return _json(apis.feriados_nacionais(ano))
    except apis.ErroAPIExterna as erro:
        return _json({"erro": str(erro)})


@tool
def consultar_pypi(pacote: str) -> str:
    """Consulta no PyPI (API pública) a versão estável mais recente de um pacote Python e as últimas
    versões publicadas. Use antes de recomendar ou validar uma biblioteca."""
    try:
        return _json(apis.consultar_pypi(pacote))
    except apis.ErroAPIExterna as erro:
        return _json({"erro": str(erro)})


@tool
def consultar_vulnerabilidades(pacote: str, versao: str) -> str:
    """Consulta na base pública OSV.dev as vulnerabilidades conhecidas que afetam uma versão específica
    de um pacote Python, com pontuação CVSS e versão em que foram corrigidas."""
    try:
        dados = apis.consultar_vulnerabilidades(pacote, versao)
    except apis.ErroAPIExterna as erro:
        return _json({"erro": str(erro)})
    dados["vulnerabilidades"] = dados["vulnerabilidades"][:5]  # as 5 mais graves bastam ao raciocínio
    dados["maior_cvss"] = max((v["cvss"] or 0 for v in dados["vulnerabilidades"]), default=0)
    return _json(dados)


@tool
def buscar_issues_github(termo: str) -> str:
    """Busca issues (abertas ou fechadas) no repositório GitHub do time que mencionem o termo
    informado, para encontrar trabalho relacionado ou duplicado."""
    try:
        return _json(apis.buscar_issues_github(termo))
    except apis.ErroAPIExterna as erro:
        return _json({"erro": str(erro)})


# ============================================================== text-to-query
@tool(description=f"""Executa uma consulta SQL de LEITURA (SELECT) no banco de backlog e devolve as linhas.
Traduza a pergunta do usuário para SQL SQLite seguindo exatamente este esquema:
{sql.DICIONARIO_DADOS}""")
def consultar_backlog_sql(consulta_sql: str) -> str:
    resultado = sql.executar_consulta(consulta_sql)
    print(f"[auditoria SQL] {resultado.get('sql')}")
    return _json(resultado)


# ============================================================== RAG
class ArgsBuscaManual(BaseModel):
    consulta_otimizada: str = Field(
        description=(
            "Reescreva a pergunta como consulta técnica densa, usando o vocabulário formal das normas "
            "(ex.: 'ramo principal protegido, solicitação de incorporação (pull request)' em vez de "
            "'subir direto na main'). Não envie a frase coloquial do usuário."
        )
    )
    documento: Optional[str] = Field(default=None, description="Opcional: restringe a uma norma (MAN-01 a MAN-07)")


@tool(args_schema=ArgsBuscaManual)
def buscar_manual_engenharia(consulta_otimizada: str, documento: Optional[str] = None) -> str:
    """Busca no Manual de Engenharia (normas MAN-01 a MAN-07: Definição de Pronto, padrões de código,
    versionamento e implantação, segurança de dependências, autenticação, planejamento e ADRs).
    Devolve trechos com fonte, chunk_id e diagnóstico de similaridade (distância L2)."""
    # Transformação de consulta: o próprio agente já reescreve a pergunta no vocabulário das normas (campo
    # consulta_otimizada). RAG_TRANSFORMACAO=multi-query+hyde acrescenta a camada híbrida da Fase 4. Padrão
    # "nenhuma": na avaliação de ponta a ponta (Fase 5) a camada extra não melhorou a corretude e custou ~7,6 s
    # a mais por resposta. O agente de recuperação da Fase 4, que recebe a pergunta literal, mantém a camada.
    modo = os.getenv("RAG_TRANSFORMACAO", "nenhuma")
    if modo != "nenhuma":
        from fabrica_agentica.ferramentas.transformacao_consulta import documento_hipotetico, variacoes

        consultas = [*variacoes(consulta_otimizada), documento_hipotetico(consulta_otimizada)]
        resultados = rag.buscar_varias(consultas, k=4, documento=documento)
    else:
        consultas = [consulta_otimizada]
        resultados = rag.buscar(consulta_otimizada, k=4, documento=documento)
    aviso = None
    if not resultados or all(r["similaridade"] == "baixa" for r in resultados):
        aviso = "Similaridade baixa em todos os trechos: a norma pode não cobrir o assunto. Não invente regra."
    return _json({"consulta": consulta_otimizada, "transformacao": modo, "consultas_usadas": consultas, "aviso": aviso, "resultados": resultados})


# ============================================================== semânticas
@tool
def decompor_demanda(demanda: str, contexto: str = "") -> str:
    """Decompõe uma demanda em épico, histórias de usuário (com critérios de aceite em Gherkin e
    estimativa Fibonacci) e tarefas técnicas, seguindo o MAN-06. Informe em `contexto` as regras e
    restrições já descobertas (normas, capacidade, bibliotecas)."""
    estruturador = criar_llm("auxiliar").with_structured_output(PlanoTrabalho, method="json_schema")
    prompt = (
        "Você é um líder técnico sênior. Decomponha a demanda em um épico com 2 a 5 histórias de usuário "
        "independentes. Cada história: título 'Como <papel>, quero <ação>, para <benefício>', 2 a 4 critérios "
        "de aceite em Gherkin (Dado/Quando/Então), estimativa em Fibonacci de no máximo 8 pontos e tarefas de "
        "até um dia. Respeite as restrições do contexto. Escreva em português do Brasil.\n\n"
        f"DEMANDA: {demanda}\n\nCONTEXTO E RESTRIÇÕES: {contexto or '(nenhum)'}"
    )
    plano: PlanoTrabalho = estruturador.invoke(prompt)
    validacoes = [hardcoded.validar_estimativa(h.pontos) | {"historia": h.titulo} for h in plano.historias]
    return _json({"plano": plano.model_dump(), "total_pontos": sum(h.pontos for h in plano.historias), "validacao_estimativas": validacoes})


@tool
def resumir_texto_tecnico(texto: str, foco: str = "riscos e decisões") -> str:
    """Resume um texto técnico longo (issues, trechos de normas, saídas de ferramentas) em até 5 tópicos,
    com o foco indicado."""
    resposta = criar_llm("auxiliar").invoke(
        f"Resuma em até 5 tópicos curtos, em português, com foco em {foco}. Não acrescente fatos.\n\nTEXTO:\n{texto}"
    )
    return texto_de(resposta)


# ============================================================== ação
class ArgsRegistro(BaseModel):
    projeto: str = Field(description="Projeto do backlog: Portal, PagaFacil ou AppCampo")
    numero_sprint: Optional[int] = Field(default=None, description="Sprint de destino; omita para deixar no backlog")
    plano: PlanoTrabalho = Field(description="O plano de trabalho a registrar (épico e histórias)")
    abrir_issues: bool = Field(default=True, description="Também abrir uma issue no GitHub para cada história")


@tool(args_schema=ArgsRegistro)
def propor_registro_backlog(projeto: str, plano: PlanoTrabalho, numero_sprint: Optional[int] = None, abrir_issues: bool = True) -> str:
    """PROPÕE o registro das histórias no backlog (e a abertura de issues no GitHub). Não grava nada:
    cria uma pendência que só é executada após confirmação humana na interface. Use somente depois de
    apresentar o plano e quando o usuário pedir para registrar."""
    if isinstance(plano, dict):
        plano = PlanoTrabalho.model_validate(plano)
    return _json(acoes.propor_registro(plano, projeto, numero_sprint, abrir_issues))


FERRAMENTAS = [
    calcular_capacidade_sprint,
    comparar_versoes,
    classificar_cvss,
    consultar_feriados,
    consultar_pypi,
    consultar_vulnerabilidades,
    buscar_issues_github,
    consultar_backlog_sql,
    buscar_manual_engenharia,
    decompor_demanda,
    resumir_texto_tecnico,
    propor_registro_backlog,
]

TIPOS = {
    "calcular_capacidade_sprint": "hardcoded",
    "comparar_versoes": "hardcoded",
    "classificar_cvss": "hardcoded",
    "consultar_feriados": "API externa",
    "consultar_pypi": "API externa",
    "consultar_vulnerabilidades": "API externa",
    "buscar_issues_github": "API externa",
    "consultar_backlog_sql": "text-to-query",
    "buscar_manual_engenharia": "RAG (FAISS)",
    "decompor_demanda": "semântica",
    "resumir_texto_tecnico": "semântica",
    "propor_registro_backlog": "ação (aprovação humana)",
}
