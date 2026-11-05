"""Esquemas Pydantic: o "contrato" das saídas estruturadas do agente."""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class AnaliseDemanda(BaseModel):
    """Saída da chain MVP (Fase 1): a triagem técnica de uma demanda."""

    resumo: str = Field(description="Resumo técnico da demanda em uma ou duas frases")
    tipo: Literal["nova_funcionalidade", "correcao", "melhoria_tecnica", "duvida"] = Field(description="Tipo de demanda")
    projeto: Optional[str] = Field(default=None, description="Projeto afetado, se citado (Portal, PagaFacil, AppCampo)")
    componentes_afetados: list[str] = Field(description="Componentes técnicos envolvidos (ex.: backend, front-end, banco)")
    complexidade: Literal["baixa", "media", "alta"] = Field(description="Complexidade estimada")
    riscos: list[str] = Field(description="Principais riscos técnicos")
    perguntas_em_aberto: list[str] = Field(description="Perguntas a esclarecer com o solicitante")
    proximos_passos: list[str] = Field(description="Próximos passos recomendados ao líder técnico")


class Historia(BaseModel):
    titulo: str = Field(description="Formato: 'Como <papel>, quero <ação>, para <benefício>'")
    criterios_aceite: list[str] = Field(description="Critérios no formato Gherkin: 'Dado ..., quando ..., então ...'")
    pontos: int = Field(description="Estimativa em pontos Fibonacci (1, 2, 3, 5, 8)")
    tarefas: list[str] = Field(description="Tarefas técnicas de até um dia cada")


class PlanoTrabalho(BaseModel):
    """Decomposição hierárquica de uma demanda (MAN-06 §5): épico -> histórias -> tarefas."""

    epico: str = Field(description="Nome curto do épico")
    objetivo: str = Field(description="Objetivo de negócio do épico")
    historias: list[Historia] = Field(description="Histórias de usuário independentes e pequenas")
    riscos: list[str] = Field(description="Riscos e dependências técnicas")


class IntencaoEntidades(BaseModel):
    """Reconhecimento de intenção e extração de entidades de uma mensagem do usuário."""

    intencao: Literal["planejar_demanda", "consultar_backlog", "checar_dependencia", "consultar_padrao", "conversa_geral"] = Field(
        description="Intenção principal da mensagem"
    )
    projeto: Optional[str] = Field(default=None, description="Projeto citado: Portal, PagaFacil ou AppCampo")
    sprint: Optional[int] = Field(default=None, description="Número da sprint citada")
    pacote: Optional[str] = Field(default=None, description="Pacote/biblioteca de software citado")
    versao: Optional[str] = Field(default=None, description="Versão de pacote citada")
    prioridade: Optional[Literal["alta", "media", "baixa"]] = Field(default=None, description="Prioridade citada")
    pessoa: Optional[str] = Field(default=None, description="Integrante do time citado")
