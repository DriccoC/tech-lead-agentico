"""Camada de verificação e validação (V&V) das respostas do agente.

Quatro etapas, sobre a resposta final e as EVIDÊNCIAS do turno (saídas das ferramentas):

1. EXTRAÇÃO de afirmações verificáveis (LLM auxiliar, saída estruturada).
2. FACT-CHECK DETERMINÍSTICO: todo número de uma afirmação precisa aparecer nas
   evidências (com tolerância); números ausentes ficam "não rastreados" (podem ser contas
   do agente ou invenção — as etapas 3 e 4 decidem).
3. NLI com modelo dedicado (mDeBERTa-v3 multilíngue treinado em XNLI/MNLI, local) nas
   afirmações de FATO DIRETO: a premissa são as frases de evidência mais parecidas; o modelo
   dá sustentação (entailment), contradição ou neutralidade.
4. COERÊNCIA LÓGICA (LLM juiz): contradição entre premissa e conclusão, erro de cálculo,
   violação de escopo e afirmação sem evidência, olhando a resposta inteira.

Por que separar: modelos NLI checam bem fatos enunciados ("saldo de 25" x "saldo de 9"),
mas não fazem aritmética — "faltam 2 pontos" (11 − 9) aparece como contradição para eles.
Conclusões derivadas (cabe/não cabe, faltam, sobram) vão para o juiz de coerência.

Aprovação: nenhuma contradição NLI forte em fato direto e resposta coerente segundo o juiz.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal, Optional

import numpy as np
from pydantic import BaseModel, Field

from fabrica_agentica.config import MODELO_NLI, criar_embeddings, criar_llm
from fabrica_agentica.verificacao.evidencias import numeros

LIMIAR_NLI = 0.60
LIMIAR_REPROVACAO = 0.80  # contradição NLI que reprova a resposta


class Afirmacao(BaseModel):
    texto: str = Field(description="Afirmação autocontida, copiada ou parafraseada fielmente da resposta")
    tipo: Literal["fato", "conclusao"] = Field(
        description="fato = enuncia um valor, regra, versão ou estado vindo das fontes; conclusao = deriva de contas ou "
        "raciocínio (cabe/não cabe, faltam/sobram X, portanto, recomendação)"
    )


class ListaAfirmacoes(BaseModel):
    afirmacoes: list[Afirmacao] = Field(description="Até 10 afirmações factuais verificáveis da resposta")


class RelatorioCoerencia(BaseModel):
    veredito: Literal["APOIA", "REFUTA", "NEUTRA"] = Field(description="As evidências apoiam, refutam ou não decidem a resposta")
    coerente: bool = Field(description="False se houver contradição interna, erro de cálculo ou conclusão que não segue das premissas")
    falhas: list[Literal["contradicao_premissa_conclusao", "erro_de_calculo", "violacao_de_escopo", "afirmacao_sem_evidencia", "nenhuma"]] = Field(
        description="Falhas lógicas detectadas"
    )
    justificativa: str = Field(description="Justificativa técnica curta, em português, citando os trechos problemáticos")


class AfirmacaoVerificada(BaseModel):
    texto: str
    tipo: str
    numeros_rastreados: Optional[bool] = None
    nli: str = "neutra"
    prob_sustentacao: float = 0.0
    prob_contradicao: float = 0.0
    premissa: str = ""


class RelatorioVerificacao(BaseModel):
    aprovado: bool
    motivos: list[str]
    alertas: list[str] = []
    afirmacoes: list[AfirmacaoVerificada]
    coerencia: RelatorioCoerencia

    def resumo(self) -> str:
        cont = sum(a.nli == "contradição" for a in self.afirmacoes)
        sust = sum(a.nli == "sustentada" for a in self.afirmacoes)
        selo = "APROVADA" if self.aprovado else "REPROVADA"
        return (f"{selo} | {len(self.afirmacoes)} afirmações: {sust} sustentadas, {cont} contraditas | "
                f"coerência: {'ok' if self.coerencia.coerente else ', '.join(self.coerencia.falhas)}")


@lru_cache(maxsize=1)
def _modelo_nli():
    from transformers import pipeline

    return pipeline("text-classification", model=MODELO_NLI, top_k=None)


def nli(premissa: str, hipotese: str) -> dict[str, float]:
    saida = _modelo_nli()({"text": premissa[:1500], "text_pair": hipotese[:500]})
    saida = saida[0] if saida and isinstance(saida[0], list) else saida
    return {d["label"]: float(d["score"]) for d in saida}


def _premissas(afirmacao: str, evidencias: list[str], vetores: np.ndarray, k: int = 3) -> list[str]:
    """As k frases de evidência mais parecidas com a afirmação (cada uma avaliada separadamente)."""
    if not evidencias:
        return []
    q = np.asarray(criar_embeddings().embed_query(afirmacao))
    return [evidencias[i] for i in np.argsort(-(vetores @ q))[:k]]


def nli_agregado(afirmacao: str, premissas: list[str]) -> tuple[float, float, str]:
    """NLI frase a frase: sustentada se ALGUMA premissa implica a afirmação; contradição só se a premissa mais
    parecida a contradiz e nenhuma a sustenta (evita falsas contradições por mistura de frases)."""
    resultados = [nli(p, afirmacao) for p in premissas]
    melhor = max(range(len(resultados)), key=lambda i: resultados[i].get("entailment", 0.0))
    p_ent = resultados[melhor].get("entailment", 0.0)
    p_con = resultados[0].get("contradiction", 0.0) if p_ent < LIMIAR_NLI else 0.0
    return p_ent, p_con, premissas[melhor] if p_ent >= LIMIAR_NLI else premissas[0]


def extrair_afirmacoes(resposta: str) -> list[Afirmacao]:
    extrator = criar_llm("auxiliar").with_structured_output(ListaAfirmacoes, method="json_schema")
    lista: ListaAfirmacoes = extrator.invoke(
        "Extraia da RESPOSTA até 10 afirmações verificáveis (números, regras, versões e segurança de bibliotecas, "
        "e conclusões como 'cabe/não cabe'). Classifique cada uma como 'fato' (enuncia um valor/regra/estado) ou "
        "'conclusao' (deriva de conta ou raciocínio). Cada afirmação deve ser autocontida (inclua sprint, projeto, "
        "pacote) e fiel ao que a resposta diz — inclusive se estiver errada. Ignore cortesias, ofertas de ajuda, "
        "recomendações de próximos passos e afirmações sobre o próprio processo do agente (o que ele consultou ou não)."
        "\n\nRESPOSTA:\n" + resposta[:6000]
    )
    return lista.afirmacoes[:10]


def avaliar_coerencia(resposta: str, evidencias: list[str]) -> RelatorioCoerencia:
    juiz = criar_llm("juiz").with_structured_output(RelatorioCoerencia, method="json_schema")
    return juiz.invoke(
        "Atue como auditor de Inferência de Linguagem Natural. Compare a RESPOSTA de um agente com as EVIDÊNCIAS "
        "(saídas das ferramentas, fonte de verdade). Verifique: (1) cálculos (ex.: comparar total do plano com o "
        "saldo); (2) contradição entre premissa e conclusão, inclusive contradição interna (dizer 'cabe' e depois "
        "'não cabe'); (3) violação de escopo (afirmar regras ou fatos fora das evidências); (4) afirmações sem "
        "evidência. Contas corretas feitas a partir das evidências NÃO são falha. As evidências incluem tudo o que o "
        "agente observou na sessão (inclusive turnos anteriores), as regras do agente e memórias. Marque coerente=false "
        "SOMENTE para contradição premissa-conclusão ou erro de cálculo; detalhes secundários sem fonte entram em "
        "falhas como afirmacao_sem_evidencia/violacao_de_escopo, mas não tornam a resposta incoerente. "
        "Responda em português.\n\n"
        "EVIDÊNCIAS:\n- " + "\n- ".join(evidencias[:150]) + f"\n\nRESPOSTA:\n{resposta[:6000]}"
    )


def verificar(resposta: str, evidencias: list[str]) -> RelatorioVerificacao:
    numeros_evidencia = set().union(*(numeros(e) for e in evidencias)) if evidencias else set()
    vetores = np.asarray(criar_embeddings().embed_documents(evidencias)) if evidencias else np.zeros((0, 1))
    verificadas: list[AfirmacaoVerificada] = []
    for af in extrair_afirmacoes(resposta):
        premissas = _premissas(af.texto, evidencias, vetores)
        nums = numeros(af.texto)
        rastreados = all(any(abs(n - e) < 0.011 for e in numeros_evidencia) for n in nums) if nums else None
        premissa = ""
        if af.tipo == "fato" and premissas:
            p_ent, p_con, premissa = nli_agregado(af.texto, premissas)
            rotulo = "sustentada" if p_ent >= LIMIAR_NLI else ("contradição" if p_con >= LIMIAR_NLI else "neutra")
        else:
            p_ent = p_con = 0.0
            rotulo = "conclusão (juiz)" if af.tipo == "conclusao" else "sem evidência"
        verificadas.append(AfirmacaoVerificada(
            texto=af.texto, tipo=af.tipo, numeros_rastreados=rastreados, nli=rotulo,
            prob_sustentacao=round(p_ent, 3), prob_contradicao=round(p_con, 3), premissa=premissa[:400],
        ))
    coerencia = avaliar_coerencia(resposta, evidencias)

    motivos, alertas = [], []
    for a in verificadas:
        if a.nli == "contradição" and a.prob_contradicao >= LIMIAR_REPROVACAO:
            motivos.append(f"Contradição com as evidências (NLI {a.prob_contradicao:.2f}): {a.texto}")
        elif a.tipo == "fato" and a.numeros_rastreados is False and a.nli != "sustentada":
            alertas.append(f"Número não encontrado nas evidências: {a.texto}")
    graves = [f for f in coerencia.falhas if f in ("contradicao_premissa_conclusao", "erro_de_calculo")]
    leves = [f for f in coerencia.falhas if f in ("afirmacao_sem_evidencia", "violacao_de_escopo")]
    if graves or (not coerencia.coerente and not leves):
        motivos.append(f"Incoerência lógica ({', '.join(graves) or 'incoerente'}): {coerencia.justificativa}")
    elif coerencia.veredito == "REFUTA":
        motivos.append(f"As evidências refutam a resposta: {coerencia.justificativa}")
    elif leves:
        alertas.append(f"Detalhes sem evidência ({', '.join(leves)}): {coerencia.justificativa}")
    return RelatorioVerificacao(aprovado=not motivos, motivos=motivos, alertas=alertas, afirmacoes=verificadas, coerencia=coerencia)


def feedback_para_correcao(relatorio: RelatorioVerificacao) -> str:
    return (
        "A verificação automática REPROVOU seu rascunho de resposta. Problemas encontrados:\n- "
        + "\n- ".join(relatorio.motivos)
        + "\nReescreva a resposta corrigindo APENAS esses pontos. Mantenha todas as demais informações do rascunho "
        "que estão nas evidências. Seja coerente do começo ao fim."
    )


# ------------------------------------------------------------------ heurística do modo demonstração
from fabrica_agentica.demo.roteiro import normalizar, registrar_estruturador  # noqa: E402


@registrar_estruturador("ListaAfirmacoes")
def _afirmacoes_demo(texto: str) -> dict:
    resposta = texto.split("RESPOSTA:", 1)[-1]
    import re

    frases = [f.strip(" -*") for f in re.split(r"(?<=[.!?])\s+|\n", resposta) if re.search(r"\d", f) and len(f.strip()) > 15]
    conclusao = ("cabe", "faltam", "sobram", "portanto", "recomendo")
    return {"afirmacoes": [{"texto": f[:300], "tipo": "conclusao" if any(c in normalizar(f) for c in conclusao) else "fato"} for f in frases[:10]]}


@registrar_estruturador("RelatorioCoerencia")
def _coerencia_demo(texto: str) -> dict:
    resposta = normalizar(texto.split("RESPOSTA:", 1)[-1])
    contradiz = ("ainda cabe" in resposta or "sim, cabe" in resposta) and "nao cabe" in resposta
    return {
        "veredito": "REFUTA" if contradiz else "APOIA",
        "coerente": not contradiz,
        "falhas": ["contradicao_premissa_conclusao"] if contradiz else ["nenhuma"],
        "justificativa": "[demo] A resposta afirma que cabe e que não cabe." if contradiz else "[demo] Sem contradição interna detectada por regra.",
    }
