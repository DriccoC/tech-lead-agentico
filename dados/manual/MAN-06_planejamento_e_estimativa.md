# MAN-06 — Norma de Planejamento de Iterações e Estimativa

Código: MAN-06 · Versão 2.0 · Vigência: 01/07/2026 · Responsável: Escritório Ágil da NovaForja Software (empresa fictícia)

## 1. Iterações
As iterações (sprints) têm duração de duas semanas, de segunda-feira a sexta-feira da semana seguinte. Feriados nacionais que caiam em dias úteis são descontados dos dias disponíveis.

## 2. Estimativa
- As histórias são estimadas em pontos na sequência de Fibonacci (1, 2, 3, 5, 8, 13).
- Histórias estimadas em mais de 8 pontos devem ser decompostas antes de entrar em uma sprint.
- Toda história deve possuir critérios de aceite no formato Gherkin antes do planejamento.

## 3. Cálculo de capacidade da sprint
A capacidade é calculada pela fórmula:

capacidade bruta = soma, para cada integrante, de (dias úteis da sprint − dias de ausência) × fator de foco × 1 ponto por dia ideal.

Do total bruto reserva-se 20% para correção de defeitos e imprevistos. A capacidade líquida (80% da bruta) é arredondada para baixo. O saldo disponível para novas histórias é a capacidade líquida menos os pontos já comprometidos na sprint.

## 4. Priorização
- Defeitos de severidade crítica têm precedência sobre qualquer história.
- Itens com obrigação legal ou regulatória (como LGPD) têm prioridade alta.
- A ordem do backlog é responsabilidade do responsável de produto; o líder técnico valida a viabilidade.

## 5. Decomposição de demandas
Demandas amplas são organizadas em épicos, decompostos em histórias de usuário independentes, negociáveis, valiosas, estimáveis, pequenas e testáveis, e estas em tarefas técnicas de no máximo um dia de trabalho.
