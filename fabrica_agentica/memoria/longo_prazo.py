"""Memória de longo prazo (CoALA): semântica e episódica, persistente entre sessões.

- SEMÂNTICA: fatos e preferências duráveis ("o usuário prefere histórias de até 5 pontos",
  "o Portal usa FastAPI").
- EPISÓDICA: o que aconteceu em sessões anteriores ("em 05/11 planejamos o login com
  Google: 3 histórias, 11 pontos; Bruno fora da sprint 13").
- (PROCEDURAL fica no system prompt e nas ferramentas hardcoded: regras do MAN-01/MAN-06.)

Armazenamento: SQLite (dados/memoria.db) com o texto, os metadados e o vetor de
embedding. Recuperação por similaridade de cosseno (vetores normalizados). Atualização:
se um fato novo do mesmo tipo e escopo for quase idêntico a um existente (cosseno >=
0,90), o existente é ATUALIZADO em vez de duplicado.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, Field

from fabrica_agentica.config import CAMINHO_MEMORIA, criar_embeddings, criar_llm

LIMIAR_DUPLICATA = 0.90  # acima: mesma memória, atualiza direto
LIMIAR_CANDIDATA = 0.30  # as 3 mais parecidas acima disso vão a um LLM que decide ADICIONAR ou ATUALIZAR (como no Mem0)
LIMIAR_RELEVANCIA = 0.35


class Fato(BaseModel):
    tipo: Literal["semantica", "episodica"] = Field(description="semantica = fato/preferência durável; episodica = acontecimento/decisão da sessão")
    conteudo: str = Field(description="Frase curta, autocontida e em português (inclua projeto, sprint, números)")


class DecisaoAtualizacao(BaseModel):
    acao: Literal["adicionar", "atualizar"] = Field(description="atualizar se a NOVA trata do MESMO assunto de uma existente e a atualiza/contradiz")
    memoria_id: Optional[int] = Field(default=None, description="id da memória existente a atualizar (só quando acao = atualizar)")


class FatosExtraidos(BaseModel):
    fatos: list[Fato] = Field(description="Fatos duráveis que valem para conversas futuras; lista vazia se não houver")


@dataclass
class Memoria:
    memoria_id: int
    tipo: str
    escopo: str
    conteudo: str
    atualizado_em: str
    similaridade: float = 0.0


class MemoriaLongoPrazo:
    def __init__(self, escopo: str = "geral", caminho=CAMINHO_MEMORIA) -> None:
        self.escopo = escopo  # usuário ou equipe dona das memórias
        self.caminho = caminho
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.execute(
                """CREATE TABLE IF NOT EXISTS memorias (
                       memoria_id INTEGER PRIMARY KEY AUTOINCREMENT, tipo TEXT, escopo TEXT, conteudo TEXT,
                       vetor TEXT, criado_em TEXT, atualizado_em TEXT, acessos INTEGER DEFAULT 0)"""
            )

    def _conn(self) -> sqlite3.Connection:
        return sqlite3.connect(self.caminho)

    @staticmethod
    def _vetor(texto: str) -> np.ndarray:
        return np.asarray(criar_embeddings().embed_query(texto), dtype=np.float32)

    def _todas(self, tipo: Optional[str] = None) -> list[tuple]:
        sql = "SELECT memoria_id, tipo, escopo, conteudo, vetor, atualizado_em FROM memorias WHERE escopo = ?"
        params: list = [self.escopo]
        if tipo:
            sql += " AND tipo = ?"
            params.append(tipo)
        with self._conn() as conn:
            return conn.execute(sql, params).fetchall()

    # ------------------------------------------------------------------ escrita
    def lembrar(self, conteudo: str, tipo: str = "semantica") -> dict:
        """Grava um fato; se já existir um quase igual, atualiza-o (sem duplicar)."""
        vetor = self._vetor(conteudo)
        agora = datetime.now().isoformat(timespec="seconds")
        candidatos = sorted(
            ((float(np.dot(vetor, np.asarray(json.loads(v)))), mid, texto) for mid, _, _, texto, v, _ in self._todas(tipo)),
            reverse=True,
        )
        candidatos = [c for c in candidatos if c[0] >= LIMIAR_CANDIDATA][:3]
        alvo = None
        if candidatos and candidatos[0][0] >= LIMIAR_DUPLICATA:
            alvo = candidatos[0]
        elif candidatos:
            escolhido = self._decidir(conteudo, candidatos)
            alvo = next((c for c in candidatos if c[1] == escolhido), None)
        if alvo is not None:
            similaridade, memoria_id, texto = alvo
            with self._conn() as conn:
                conn.execute(
                    "UPDATE memorias SET conteudo = ?, vetor = ?, atualizado_em = ? WHERE memoria_id = ?",
                    (conteudo, json.dumps(vetor.tolist()), agora, memoria_id),
                )
            return {"acao": "atualizada", "memoria_id": memoria_id, "antes": texto, "depois": conteudo, "similaridade": round(similaridade, 3)}
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO memorias (tipo, escopo, conteudo, vetor, criado_em, atualizado_em) VALUES (?,?,?,?,?,?)",
                (tipo, self.escopo, conteudo, json.dumps(vetor.tolist()), agora, agora),
            )
        return {"acao": "criada", "memoria_id": cur.lastrowid, "conteudo": conteudo}

    @staticmethod
    def _decidir(nova: str, candidatos: list[tuple]) -> Optional[int]:
        """Pergunta ao LLM se a nova memória atualiza alguma das existentes (id) ou deve ser adicionada (None)."""
        existentes = "\n".join(f"id={mid}: {texto}" for _, mid, texto in candidatos)
        juiz = criar_llm("auxiliar").with_structured_output(DecisaoAtualizacao, method="json_schema")
        decisao: DecisaoAtualizacao = juiz.invoke(
            "Você gerencia a memória de longo prazo de um assistente. Decida se a NOVA memória trata do MESMO assunto "
            "de uma memória EXISTENTE e a atualiza ou contradiz (ex.: uma preferência que mudou) -> acao=atualizar com o "
            "id; se for um fato diferente -> acao=adicionar.\n"
            f"EXISTENTES:\n{existentes}\n\nNOVA: {nova}"
        )
        return decisao.memoria_id if decisao.acao == "atualizar" else None

    def esquecer_tudo(self) -> None:
        with self._conn() as conn:
            conn.execute("DELETE FROM memorias WHERE escopo = ?", (self.escopo,))

    # ------------------------------------------------------------------ leitura
    def recuperar(self, consulta: str, k: int = 4, tipo: Optional[str] = None) -> list[Memoria]:
        """Busca vetorial: as k memórias mais relevantes acima do limiar de relevância."""
        linhas = self._todas(tipo)
        if not linhas:
            return []
        q = self._vetor(consulta)
        pontuadas = []
        for memoria_id, tipo_m, escopo, conteudo, vetor_json, atualizado in linhas:
            sim = float(np.dot(q, np.asarray(json.loads(vetor_json))))
            if sim >= LIMIAR_RELEVANCIA:
                pontuadas.append(Memoria(memoria_id, tipo_m, escopo, conteudo, atualizado, round(sim, 3)))
        pontuadas.sort(key=lambda m: m.similaridade, reverse=True)
        escolhidas = pontuadas[:k]
        # Recência + relevância: o episódio mais recente sempre acompanha a recuperação, para perguntas como
        # "o que fizemos da última vez?", que têm baixa similaridade lexical com o texto do episódio.
        episodios = [l for l in linhas if l[1] == "episodica"]
        if episodios and tipo in (None, "episodica"):
            recente = max(episodios, key=lambda l: l[5])
            if all(m.memoria_id != recente[0] for m in escolhidas):
                sim = float(np.dot(q, np.asarray(json.loads(recente[4]))))
                escolhidas.append(Memoria(recente[0], "episodica", recente[2], f"(sessão mais recente) {recente[3]}", recente[5], round(sim, 3)))
        if escolhidas:
            with self._conn() as conn:
                conn.executemany("UPDATE memorias SET acessos = acessos + 1 WHERE memoria_id = ?", [(m.memoria_id,) for m in escolhidas])
        return escolhidas

    def listar(self) -> list[dict]:
        return [{"id": l[0], "tipo": l[1], "conteudo": l[3], "atualizado_em": l[5]} for l in self._todas()]

    @staticmethod
    def formatar(memorias: list[Memoria]) -> str:
        if not memorias:
            return "(nenhuma memória relevante)"
        return "\n".join(f"- [{m.tipo}, {m.atualizado_em[:10]}, sim={m.similaridade}] {m.conteudo}" for m in memorias)

    # ------------------------------------------------------------------ extração automática
    def extrair_e_gravar(self, mensagem_usuario: str, resposta_agente: str) -> list[dict]:
        """Usa o LLM auxiliar para extrair fatos duráveis do turno e gravá-los."""
        extrator = criar_llm("auxiliar").with_structured_output(FatosExtraidos, method="json_schema")
        prompt = (
            "Extraia apenas fatos que valham para CONVERSAS FUTURAS e que NÃO estejam em outra fonte: preferências e "
            "papel do usuário, convenções do time, e decisões tomadas ou propostas na sessão (planos, pessoas retiradas "
            "de sprint, bibliotecas escolhidas). NÃO grave: regras das normas do manual (já estão na base de "
            "conhecimento), números que as ferramentas recalculam (capacidade, saldo, versões, vulnerabilidades), "
            "cumprimentos e perguntas. Normalmente são 0 a 2 fatos por turno. "
            "Cada fato: frase curta, autocontida, em português, com projeto/sprint/números quando houver.\n\n"
            f"USUÁRIO: {mensagem_usuario}\n\nAGENTE: {resposta_agente[:2500]}"
        )
        extraidos: FatosExtraidos = extrator.invoke(prompt)
        return [self.lembrar(f.conteudo, f.tipo) for f in extraidos.fatos]

    def registrar_episodio(self, transcricao: str) -> dict:
        """Resume a sessão inteira num episódio (memória episódica) ao encerrar."""
        resposta = criar_llm("auxiliar").invoke(
            "Resuma esta sessão de planejamento em UMA frase em português, começando pela data de hoje "
            f"({datetime.now():%d/%m/%Y}), com projeto, sprint, decisões e números finais.\n\n{transcricao[-6000:]}"
        )
        from fabrica_agentica.config import texto_de

        return self.lembrar(texto_de(resposta), "episodica")


# ------------------------------------------------------------------ heurística do modo demonstração
from fabrica_agentica.demo.roteiro import normalizar, registrar_estruturador  # noqa: E402


@registrar_estruturador("DecisaoAtualizacao")
def _decisao_demo(texto: str) -> dict:
    nova = set(normalizar(texto.rsplit("NOVA:", 1)[-1]).split())
    for linha in texto.split("EXISTENTES:", 1)[-1].split("NOVA:", 1)[0].strip().splitlines():
        mid, _, conteudo = linha.partition(": ")
        palavras = set(normalizar(conteudo).split())
        if nova and len(nova & palavras) / len(nova) >= 0.6:
            return {"acao": "atualizar", "memoria_id": int(mid.replace("id=", ""))}
    return {"acao": "adicionar", "memoria_id": None}


@registrar_estruturador("FatosExtraidos")
def _fatos_demo(texto: str) -> dict:
    usuario = texto.split("USUÁRIO:", 1)[-1].split("AGENTE:", 1)[0].strip()
    fatos = []
    for frase in [f.strip() for f in usuario.replace("!", ".").split(".") if f.strip()]:
        t = normalizar(frase)
        if any(k in t for k in ("prefiro", "sou o", "sou a", "meu nome", "trabalho no", "sempre", "nunca")):
            fatos.append({"tipo": "semantica", "conteudo": f"O usuário disse: {frase}."})
        elif any(k in t for k in ("decid", "vamos usar", "tirarmos", "tirar o", "aprov")):
            fatos.append({"tipo": "episodica", "conteudo": f"Decisão da sessão: {frase}."})
    return {"fatos": fatos}
