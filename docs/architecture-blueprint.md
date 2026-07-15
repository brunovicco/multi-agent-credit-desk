# Mesa de Crédito Multi-Agente — Blueprint de Arquitetura

**Versão:** 0.2 · **Data:** 2026-07-15 · **Autor:** Vicco
**Status:** Aprovado para fase de scaffold (sem implementação de agentes)
**Mudanças na 0.2:** ADR-001 revisado (monorepo + libs extraídas), ADR-007 ajustado
(transparência do mock Open Finance), ADR-008 novo (harness como base), Python 3.13.

Plataforma distribuída de agentes que analisa solicitações de crédito PJ e produz
uma **decisão auditável** de concessão, com evidências reproduzíveis.

O projeto demonstra:

- agentes independentes comunicando-se por **A2A** (Agent Cards, tasks, artifacts);
- ferramentas e fontes acessadas via **MCP** (incluindo Open Finance BR MCP Server);
- **roteamento automático de modelos** em três camadas separadas;
- **trace distribuído** ponta a ponta (OTel → Datadog + Langfuse);
- **logs JSON padronizados** e correlacionados com traces;
- fallback entre modelos e deployments com restrições de compliance;
- **núcleo determinístico** de score e política de alçada (zero LLM no core);
- evidence bundle reproduzível por solicitação.

---

## 1. ADRs

Formato curto: Contexto → Decisão → Consequências. Cada ADR abaixo foi extraído para um arquivo
canônico em inglês em `docs/adr/`; este documento permanece como fonte histórica em português, não
como registro canônico. As seções abaixo estão preservadas para contexto narrativo.

| ADR do blueprint | Arquivo canônico |
|---|---|
| ADR-000 | [`docs/adr/0002-domain-credit-desk-vs-ai-change-guardian.md`](adr/0002-domain-credit-desk-vs-ai-change-guardian.md) |
| ADR-001 | [`docs/adr/0003-monorepo-with-extracted-libraries.md`](adr/0003-monorepo-with-extracted-libraries.md) |
| ADR-002 | [`docs/adr/0004-three-separated-routing-layers.md`](adr/0004-three-separated-routing-layers.md) |
| ADR-003 | [`docs/adr/0005-policy-based-deterministic-router-mvp.md`](adr/0005-policy-based-deterministic-router-mvp.md) |
| ADR-004 | [`docs/adr/0006-observability-otel-fanout-datadog-langfuse.md`](adr/0006-observability-otel-fanout-datadog-langfuse.md) |
| ADR-005 | [`docs/adr/0007-telemetry-without-sensitive-content.md`](adr/0007-telemetry-without-sensitive-content.md) |
| ADR-006 | [`docs/adr/0008-deterministic-core-without-llm.md`](adr/0008-deterministic-core-without-llm.md) |
| ADR-007 | [`docs/adr/0009-reuse-existing-mcp-servers.md`](adr/0009-reuse-existing-mcp-servers.md) |
| ADR-008 | [`docs/adr/0010-claude-code-harness-as-base.md`](adr/0010-claude-code-harness-as-base.md) |

### ADR-000 — Domínio: Mesa de Crédito (vs. AI Change Guardian)

**Contexto.** Dois domínios candidatos com o mesmo conteúdo de engenharia
(A2A, MCP, routing, observabilidade): revisão de mudanças de software
(Change Guardian) e análise de crédito PJ (Mesa de Crédito).

**Decisão.** Mesa de Crédito.

**Justificativa.**
1. Alinhamento com a narrativa profissional (20+ anos em banking/financial no Brasil) e com as vagas-alvo (BTG, EY, instituições reguladas).
2. Reuso direto do **Open Finance BR MCP Server** já open-sourced — diferencial que nenhuma demo genérica tem.
3. O domínio de crédito força os requisitos mais interessantes: classificação de dados (LGPD, LC 105/2001), restrição modelo local vs. externo, decisão determinística de alçada, trilha de auditoria.
4. AI code review é um espaço saturado; mesa de crédito com A2A + trace distribuído é praticamente inédito como demo pública.

**Consequências.** Dados de clientes serão sintéticos (mock BCB Open Finance).
O README deve deixar explícito que é ambiente demonstrativo. Perde-se a
facilidade de demo com PRs reais do GitHub — aceito.

### ADR-001 — Monorepo da aplicação + bibliotecas extraídas (rev. na 0.2)

**Contexto.** Proposta original previa 12 repositórios; a v0.1 deste documento
decidiu monorepo puro. Revisão: repositórios separados têm valor real de
portfólio (visibilidade no perfil, README próprio, instalabilidade
independente) — mas o critério de corte não pode ser espelhar a arquitetura
em repos.

**Decisão.** Critério de extração: **tem valor standalone fora da Mesa de
Crédito?** Resultado — 4 repositórios visíveis:

| Repositório | Conteúdo | Papel |
|---|---|---|
| `multi-agent-credit-desk` | Aplicação (monorepo uv workspace) | Demo principal, `docker compose up` |
| `a2a-otel-kit` | Lib: OTel init, propagação `traceparent`, structlog JSON, sanitização, interceptors A2A/MCP | pip-installable, genérica |
| `policy-model-router` | Serviço: restrições eliminatórias + tabela de workloads + registro de decisão | Imagem publicada (GHCR), genérico p/ qualquer stack LiteLLM |
| `openfinance-br-mcp` | MCP server (já existente, mock) | Fonte de dados Open Finance |

O monorepo consome `a2a-otel-kit` como **dependência pinada** (release tags +
changelog, atualização via PR) e `policy-model-router` como **imagem no
compose** — demonstrando versionamento de contrato entre repositórios de
verdade, sem pagar o custo de 12.

Permanecem no monorepo (sem audiência standalone): orchestrator, 4 agentes,
`credit-core`, `contracts`, bureau-mcp, policy-mcp, infra.

**Consequências.** Overhead de release só onde há valor. Fatiar os agentes
mataria a experiência de avaliação em um comando. Interfaces das libs em
0.x podem mudar rápido no início — mitigado por testes de contrato no
monorepo e releases frequentes.

### ADR-002 — Três camadas de roteamento separadas

**Contexto.** "Roteamento" mistura três decisões distintas.

**Decisão.**

| Camada | Pergunta | Responsável |
|---|---|---|
| Agent routing | Qual agente executa a atividade? | `orchestrator` (via skills dos Agent Cards) |
| Model routing | Qual grupo de modelo atende o workload? | `model-router` (serviço de infraestrutura) |
| Provider routing | Qual deployment/provedor atende a chamada? | LiteLLM Gateway |

O `model-router` **não é um agente A2A** — é infraestrutura, chamado por HTTP
pelos agentes antes de cada chamada de LLM.

**Consequências.** Troca do mecanismo de model routing (ex.: adicionar
RouteLLM na Fase 3) não altera agentes nem o protocolo A2A. LiteLLM cuida de
abstração de provedores, retries, cooldowns e fallback dentro do grupo.

### ADR-003 — Router determinístico policy-based no MVP (sem score ponderado)

**Contexto.** A proposta original incluía função de score
(`capability_fit × 0.35 + expected_quality × 0.25 + ...`). Termos como
`expected_quality` e `historical_success` exigem dados de avaliação que não
existem no dia 1.

**Decisão.** MVP roteia em dois passos:

1. **Restrições obrigatórias (eliminatórias):** classificação de dados,
   localização de processamento, local vs. externo, structured output,
   tool calling, janela de contexto, custo máximo, latência máxima,
   disponibilidade, allowlist por agente.
2. **Tabela declarativa workload → model_group** (YAML versionado).

O **formato do registro de decisão** (com `rejected_candidates` e razões)
entra desde o dia 1. A função de score ponderado fica na Fase 3, quando
houver dados de avaliação por workload.

**Consequências.** Router 100% explicável e testável por tabela-verdade.
Nenhum número inventado fingindo ser engenharia.

### ADR-004 — Observabilidade: OTel com fan-out para Datadog e Langfuse

**Contexto.** Datadog é keyword de mercado, mas exige conta paga e quem clona
o repo não reproduz as traces. Langfuse é self-hosted e cobre a camada genAI
(custo, tokens, evals), mas não é APM de infraestrutura.

**Decisão.** Instrumentação exclusivamente **OpenTelemetry** (SDK + semantic
conventions `gen_ai.*`), propagação **W3C `traceparent`** em todas as chamadas
(A2A, model-router, MCP, filas). Um **OTel Collector** central faz fan-out:

- exporter **Datadog** (APM + LLM Observability) — ativado por perfil, para o ambiente com conta;
- exporter **OTLP → Langfuse** self-hosted — sempre ativo no compose, reproduzível por qualquer avaliador.

Callback nativo LiteLLM → Langfuse complementa custo/tokens por chamada.

**Consequências.** "Backend-agnostic by design" vira feature demonstrável.
O compose fica mais pesado (Langfuse v3 = Postgres + ClickHouse + Redis +
MinIO) — aceito, é fiel a produção.

### ADR-005 — Telemetria sem conteúdo sensível por padrão

**Decisão.** Prompts, respostas, documentos e dados de cliente **não** são
enviados integralmente à telemetria. Registra-se: hashes, tamanhos, contagem
de tokens, classificação de dados, metadados e referência ao artifact
armazenado de forma controlada. Captura de conteúdo completo é configurável
por ambiente (`TELEMETRY_CAPTURE_CONTENT`), desabilitada por padrão.

**Consequências.** Coerente com LGPD/LC 105 mesmo em demo. Debugging profundo
usa o artifact store, não a telemetria.

### ADR-006 — Núcleo determinístico sem LLM (guard em CI)

**Decisão.** Score de crédito, política de alçada e regras de bloqueio vivem
em `packages/credit-core`, módulo Python puro, sem nenhum import de LLM/SDK
de provedor. A lista de dependências proibidas em `scripts/validate_architecture.py` falha o
build se detectar import não permitido — ver `docs/adr/0010-claude-code-harness-as-base.md` para
o motivo de ser uma entrada no check já existente do harness, não um script novo.

LLM atua apenas nas bordas: extração de documentos, análise qualitativa de
fluxo de caixa, redação do parecer.

**Consequências.** A decisão de crédito é reproduzível e auditável por
construção. `policy.decision` no trace aponta para versão da política aplicada.

### ADR-007 — Reuso de MCP servers existentes

**Decisão.** Não escrever MCP servers do zero quando existir opção madura:

- **openfinance-br-mcp** (próprio, open-sourced) — dados bancários do cliente;
- **bureau-mcp** (novo, pequeno) — mock de bureau de crédito (score externo, negativações), justificado por não existir equivalente;
- **policy-mcp** (novo, pequeno) — catálogo versionado de políticas de crédito consultável pelos agentes.

**Transparência do mock.** O `openfinance-br-mcp` **não acessa o ecossistema
Open Finance real** (sem conta de consulta). Posicionamento honesto no README:
"implementação do protocolo MCP sobre dados sintéticos no formato Open
Finance BR". O valor demonstrável é a implementação do protocolo + o modelo
de dados BR — e vira ponto a favor: **a demo completa roda sem credencial
alguma** (nem BCB, nem Datadog).

**Consequências.** Reuso demonstra senioridade; os dois MCPs novos são
pequenos e de domínio, não infraestrutura reinventada.

### ADR-008 — `claude-python-engineering-harness` como base de todos os repos

**Contexto.** Harness próprio e público (`bootstrap.py`, scaffold
CLAUDE.md/AGENTS.md, rules path-conditional, hooks fail-closed, agents,
skills, CI com Ruff/Mypy/Pytest/Bandit/pip-audit, governança MCP,
`validate_architecture.py` com forbidden-dependency list).

**Decisão.** Todos os repositórios do projeto nascem do harness:

1. **Libs extraídas** (`a2a-otel-kit`, `policy-model-router`): `bootstrap.py`
   direto (`--git-init --lock`).
2. **Monorepo**: bootstrap na raiz **uma vez** + conversão do `pyproject.toml`
   para uv workspace. `.claude/` único na raiz, usando rules path-conditional
   por pacote (ex.: rule em `packages/credit-core/` proibindo LLM). Não
   bootstrapar por serviço — duplicaria o `.claude/` oito vezes.
3. **Guard do núcleo determinístico**: implementado como entrada na
   forbidden-dependency list do `validate_architecture.py` do harness — não
   como script novo.
4. **Governança MCP do harness ativa** (`guard_mcp.py`,
   `validate_mcp_config.py`, `/review-mcp`): o projeto consome 3 MCP servers,
   e governança de MCP passa a ser parte da demo.
5. **Python 3.13** (padrão do harness; a2a-sdk, LiteLLM e OTel suportam).

**Consequências.** Padronização entre os 4 repos vira parte da narrativa: o
harness é validado por consumo real e passa a ser o 5º item do portfólio. A
filosofia de observabilidade opt-in do harness (`docs/LLM_OBSERVABILITY.md`)
já é coerente com o ADR-005.

---

## 2. Arquitetura

### 2.1 Topologia

```
            Web UI / CLI
                 |
                 v
        Credit Orchestrator
                 |
                 |  A2A (Agent Cards, tasks, artifacts, traceparent)
    +------------+------------+
    |            |            |
    v            v            v
Cadastral     Financeiro    Risco/Compliance
 Agent          Agent          Agent
    |            |               |
    +------------+---------------+
                 |
                 v
          Decisão Agent
        (parecer + alçada)
                 |
                 v
     Decisão + Evidence Bundle
```

### 2.2 Agentes (MVP = 4)

| Agente | Responsabilidade | MCP tools | Workloads LLM |
|---|---|---|---|
| `cadastral-agent` | KYC/KYB: valida dados cadastrais, sócios, situação fiscal | bureau-mcp | `document_extraction` (fast-small) |
| `financeiro-agent` | Analisa fluxo de caixa, endividamento, faturamento via Open Finance | **Open Finance BR MCP** | `cashflow_analysis` (reasoning-medium) |
| `risco-agent` | Correlaciona achados, aplica política de crédito, identifica red flags | policy-mcp, bureau-mcp | `findings_correlation` (reasoning-strong) |
| `decisao-agent` | Executa `credit-core` (score + alçada determinísticos) e redige o parecer | policy-mcp | `opinion_drafting` (reasoning-strong), `json_repair` (fast-structured-output) |

Cadastral, Financeiro e Risco executam **em paralelo** onde não há dependência
(cadastral e financeiro são independentes; risco consome os dois). Cada agente
publica Agent Card em `/.well-known/agent.json` com skills declaradas.

### 2.3 Camada de modelos

```
Agents
  |  POST /route  {agent, workload, risk_level, data_classification, ...}
  v
model-router  ──  registro de decisão (selected + rejected_candidates)
  |
  v
LiteLLM Gateway
  |
  +--> local: vLLM (Llama/Qwen)          [data_classification >= confidential]
  +--> Groq (fast-small)
  +--> Anthropic (reasoning-strong)
  +--> fallback dentro do mesmo grupo autorizado
```

Grupos do MVP: `fast-small`, `reasoning-medium`, `reasoning-strong`,
`fast-structured-output` (alias). Regra dura: **nunca** fallback de modelo
local autorizado para provedor externo não autorizado para aquela
classificação de dados.

Metadados obrigatórios por requisição:

```json
{
  "agent": "financeiro-agent",
  "workload": "cashflow_analysis",
  "risk_level": "high",
  "data_classification": "confidential",
  "context_tokens_estimated": 24000,
  "structured_output_required": true,
  "max_latency_ms": 30000,
  "max_cost_usd": 0.15
}
```

### 2.4 Observabilidade

Hierarquia de spans de uma solicitação (uma única trace):

```
credit_review.workflow
+-- intake.normalize_request
+-- orchestrator.discover_agents
+-- a2a.task.send cadastral-agent
|   +-- agent.execute
|       +-- model.route
|       +-- llm.request
|       +-- mcp.bureau.lookup
|       +-- artifact.validate
+-- a2a.task.send financeiro-agent
|   +-- agent.execute
|       +-- model.route
|       +-- llm.request
|       +-- mcp.openfinance.accounts / transactions
|       +-- artifact.validate
+-- a2a.task.send risco-agent
|   +-- ...
+-- a2a.task.send decisao-agent
|   +-- credit_core.score          (span determinístico, sem llm.request)
|   +-- credit_core.policy_gate
|   +-- llm.request (parecer)
+-- evidence.persist
```

Identificadores funcionais além do `traceparent`: `workflow_id`, `context_id`,
`task_id`, `agent_execution_id`, `routing_decision_id`, `artifact_id`.
`trace_id` serve à observabilidade técnica; `workflow_id`/`task_id` servem à
auditoria funcional.

Tags principais: `service`, `env`, `version`, `agent.name`, `agent.skill`,
`a2a.task.id`, `workflow.id`, `model.group`, `model.provider`,
`model.deployment`, `routing.reason`, `artifact.type`, `policy.decision`,
`data.classification`, `error.type`.

### 2.5 Logs

`structlog` JSON, schema único versionado em `packages/contracts`
(`schema_version`), com `trace_id`/`span_id` injetados do contexto OTel.
Todo evento relevante carrega `event_name` + `event_outcome` — mensagem livre
nunca é o único conteúdo.

Taxonomia (enum em contracts): `workflow.*`, `a2a.agent.discovered`,
`a2a.task.*`, `agent.execution.*`, `model.routing.*`,
`model.fallback.triggered`, `llm.request.*`, `mcp.tool.*`, `artifact.*`,
`policy.evaluation.completed`, `credit.decision.issued`,
`human.approval.*` (reservado — HITL entra na Fase 2).

### 2.6 Evidence bundle

Por solicitação, um pacote versionado e reproduzível contendo: request
normalizado, artifacts de cada agente (validados por JSON Schema), registros
de decisão do router, versão da política aplicada, resultado do
`credit-core`, parecer final, hashes dos insumos e ponteiro para a trace.

---

## 3. Estrutura do monorepo

```
multi-agent-credit-desk/
├── .claude/                      # harness: rules path-conditional, agents,
│                                 # skills, hooks (guard_mcp, sensitive files)
├── docs/
│   ├── adr/                      # ADR-000..008 (este documento fatiado)
│   ├── architecture.md           # diagramas (Mermaid)
│   └── demo-script.md            # roteiro de demo end-to-end
├── packages/
│   ├── contracts/                # schemas (artifacts, eventos, router), enums,
│   │                             # exemplos de payload, testes de contrato
│   └── credit-core/              # score + alçada determinísticos (zero LLM)
├── services/
│   ├── orchestrator/
│   ├── cadastral-agent/
│   ├── financeiro-agent/
│   ├── risco-agent/
│   ├── decisao-agent/
│   ├── bureau-mcp/
│   └── policy-mcp/
├── infra/
│   ├── docker-compose.yml        # serviços + policy-model-router (imagem GHCR)
│   │                             # + LiteLLM + Langfuse stack + OTel Collector
│   │                             # + openfinance-br-mcp (imagem)
│   ├── litellm/config.yaml       # model groups, fallbacks, cooldowns
│   ├── otel/collector.yaml       # fan-out: Langfuse (default) + Datadog (perfil)
│   └── routing/workloads.yaml    # tabela workload → model_group + restrições
├── scripts/
│   └── validate_architecture.py  # harness: forbidden-deps (LLM em credit-core)
├── ui/                           # dashboard mínimo (Fase 2)
├── pyproject.toml                # uv workspace (Python 3.13, base harness);
│                                 # a2a-otel-kit como dependência pinada
└── README.md
```

Repositórios irmãos (bootstrapados pelo harness, consumidos pelo monorepo):
**`a2a-otel-kit`** (dependência pip pinada em todos os serviços) e
**`policy-model-router`** (imagem publicada, referenciada no compose).
Externo já existente: **`openfinance-br-mcp`** (mock, imagem no compose).

---

## 4. Backlog por fase

### Fase 1 — MVP

**Fundação (primeiro commit em diante — observabilidade não é etapa final):**
- [ ] Bootstrap dos 3 repos via harness; conversão do monorepo para uv workspace
- [ ] Forbidden-deps no `validate_architecture.py`: LLM proibido em `credit-core` + rule path-conditional correspondente
- [ ] `packages/contracts`: schemas de artifacts, eventos, contrato do router
- [ ] `a2a-otel-kit` (repo próprio): OTel init + structlog JSON + propagação + interceptors A2A/MCP; release 0.1 pinada no monorepo
- [ ] OTel Collector com fan-out Langfuse (default) e Datadog (perfil)
- [ ] Compose base: Langfuse stack + Collector + LiteLLM + openfinance-br-mcp

**Núcleo e routing:**
- [ ] `credit-core`: score, política de alçada, regras de bloqueio + testes de tabela-verdade
- [ ] `policy-model-router` (repo próprio): restrições eliminatórias + tabela workload→grupo + registro de decisão com `rejected_candidates`; imagem publicada e referenciada no compose
- [ ] LiteLLM: 3 grupos de modelo, fallback e cooldown configurados

**Agentes e orquestração:**
- [ ] 4 agentes A2A em containers independentes, Agent Cards publicados
- [ ] Orchestrator: discovery por Agent Card, fan-out paralelo cadastral+financeiro, sequência risco→decisão
- [ ] Integração MCP: Open Finance BR MCP, bureau-mcp, policy-mcp
- [ ] Evidence bundle persistido + validação de artifacts por JSON Schema
- [ ] Demo script: solicitação aprovada, solicitação bloqueada por política, fallback com falha simulada

**Critérios de aceite do MVP:**
1. Cada agente roda em container independente e é descoberto por Agent Card.
2. Toda comunicação orchestrator↔agentes ocorre por A2A.
3. Ferramentas externas acessadas exclusivamente por MCP.
4. Model router seleciona automaticamente com justificativa registrada (incl. rejeitados).
5. Fallback demonstrado com falha simulada, sem violar restrição de classificação de dados.
6. Execução completa aparece como **uma única trace** (Langfuse; Datadog quando perfil ativo).
7. Navegação trace → logs correlacionados funciona.
8. Todos os logs seguem o schema versionado.
9. Prompts/dados de cliente não aparecem íntegros na telemetria.
10. Red flag crítico (ex.: negativação grave) provoca **bloqueio determinístico** no `credit-core`, sem LLM no caminho da decisão.
11. Evidence bundle reproduzível gerado por solicitação.

### Fase 2
- Streaming A2A (atualizações incrementais de task) e tarefas `input-required`
- **Human-in-the-loop**: aprovação de alçada por comitê (ativa `human.approval.*`)
- Persistência de tasks (retomada de workflows longos)
- Dashboard: custos por workload, decisões, fila da mesa
- Agente adicional: `garantias-agent` (avaliação de colaterais)

### Fase 3
- Função de score do router (agora com dados reais de execução) e/ou RouteLLM
- Shadow routing e A/B entre grupos de modelo
- Avaliação automática por workload (Langfuse evals) alimentando `historical_success`
- Canary de novos modelos; otimização dinâmica de custo

### Fase 4
- Kubernetes + mTLS entre agentes; Agent Cards assinados
- Multi-tenancy e quotas por agente
- Policy as code (OPA) para a política de crédito
- Agente em linguagem diferente (ex.: TypeScript) provando interop A2A

---

## 5. Riscos e mitigação

| Risco | Mitigação |
|---|---|
| Compose pesado (Langfuse v3 = 4 dependências) | Perfil `--profile lite` sem Langfuse para primeiro contato; README com requisitos |
| Escopo do MVP crescer | 4 agentes é teto; corte candidato se apertar: fundir risco+decisão |
| Dados sintéticos pouco convincentes | Gerador de cenários (3 personas PJ: saudável, alavancada, negativada) versionado no repo |
| a2a-sdk em evolução rápida | Pin de versão + camada fina de adaptação em `packages/contracts` |
| Datadog sem conta | Fan-out garante demo completa só com Langfuse; Datadog é opt-in |
| Interfaces das libs extraídas mudando no início | Versionamento 0.x, releases frequentes, testes de contrato no monorepo |

---

## 6. Próximos passos imediatos

1. Fatiar este documento em ADRs individuais (`docs/adr/`).
2. Bootstrap dos 3 repos via harness (`multi-agent-credit-desk`,
   `a2a-otel-kit`, `policy-model-router`) e conversão do monorepo para uv
   workspace — **sem implementar agentes**.
3. Escrever `workloads.yaml` e `litellm/config.yaml` iniciais.
4. Definir os 3 cenários de demo (personas PJ) em `docs/demo-script.md`.
