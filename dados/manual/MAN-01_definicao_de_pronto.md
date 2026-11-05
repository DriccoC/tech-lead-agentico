# MAN-01 — Definição de Pronto (Definition of Done)

Código: MAN-01 · Versão 3.2 · Vigência: 01/08/2026 · Responsável: Comitê de Engenharia da NovaForja Software (empresa fictícia)

## 1. Objetivo
Estabelecer os critérios mínimos que um incremento de software deve cumprir para ser considerado concluído. Nenhuma história de usuário pode ter o status alterado para "concluída" sem atender integralmente a esta norma.

## 2. Critérios obrigatórios de conclusão
1. Critérios de aceite descritos no formato Gherkin (Dado / Quando / Então) e validados pelo responsável de produto.
2. Cobertura de testes automatizados de no mínimo 80% das linhas alteradas, medida no pipeline de integração contínua.
3. Testes de contrato atualizados sempre que a história modificar uma interface pública (API REST, evento ou fila).
4. Revisão de código aprovada por pelo menos dois revisores, sendo ao menos um de nível sênior.
5. Ausência de vulnerabilidades de severidade alta ou crítica no relatório de análise de dependências (ver MAN-04).
6. Documentação técnica atualizada; decisões com impacto arquitetural devem gerar um Registro de Decisão Arquitetural (ver MAN-07).
7. Implantação bem-sucedida no ambiente de homologação, com evidência de teste exploratório registrada pela qualidade.

## 3. Critérios específicos por tipo de entrega
- Funcionalidades com dados pessoais: avaliação de impacto à proteção de dados conforme a LGPD, com aprovação do encarregado.
- Alterações de autenticação ou autorização: revisão adicional obrigatória do time de segurança (ver MAN-05).
- Interfaces de usuário: conformidade com as diretrizes de acessibilidade WCAG 2.1 nível AA.

## 4. Exceções
Exceções a esta norma exigem registro formal no quadro da sprint, com justificativa, responsável e prazo de regularização não superior a duas sprints.
