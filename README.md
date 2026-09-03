# McDuck AI — Agente Financeiro Inteligente

> Um assistente de IA Generativa para organizar o orçamento, controlar gastos e transformar objetivos financeiros em metas mensais claras.

## Sobre o projeto

O McDuck AI foi desenvolvido como projeto final do **Bootcamp Bradesco — Dados, GenAI & Cybersecurity**, da DIO. Ele ajuda pessoas que têm dificuldade para visualizar para onde o dinheiro vai, saber quanto da renda está comprometida e planejar objetivos sem perder o controle do orçamento.

O agente analisa apenas os dados informados pelo usuário ou presentes na base fictícia. Ele **não recomenda investimentos**, não promete retornos e não substitui um profissional financeiro.

## O que o McDuck AI faz

- Organiza receitas e despesas por categoria;
- calcula total gasto, valor disponível e percentual da renda comprometida;
- compara gastos com limites mensais;
- permite criar, editar e remover categorias de gastos livremente;
- apresenta gráficos de pizza e barras interativos com Plotly;
- exporta o orçamento mensal em CSV;
- identifica a categoria com maior gasto;
- calcula quanto guardar por mês para atingir uma meta;
- avalia se o valor mensal da meta cabe no orçamento disponível;
- responde perguntas em um chat com regras anti-alucinação;
- continua funcionando para cálculos essenciais mesmo sem uma LLM.

## Demonstração com os dados fictícios

| Indicador | Resultado |
|---|---:|
| Receita mensal | R$ 5.000,00 |
| Despesas | R$ 2.788,90 |
| Disponível | R$ 2.211,10 |
| Renda comprometida | 55,8% |
| Maior categoria | Moradia — R$ 1.480,00 |

Os valores são calculados pelo código a partir de data/transacoes.csv, e não pela LLM. Isso deixa os resultados reproduzíveis e reduz o risco de alucinação.

## Arquitetura

~~~mermaid
flowchart LR
    U[Usuário] --> UI[Interface Streamlit]
    UI --> CE[Motor de cálculos]
    CE --> KB[(JSON e CSV fictícios)]
    CE --> V[Validação de escopo]
    V --> UI
    UI -->|Pergunta aberta| LLM[Ollama local]
    KB --> LLM
    LLM --> V
~~~

| Camada | Tecnologia | Responsabilidade |
|---|---|---|
| Interface | Streamlit + Plotly | Painel responsivo, gráficos, chat, editor de orçamento e metas |
| Cálculos | Python | Somas, percentuais, limites e metas |
| Base | JSON e CSV | Perfil, transações e histórico fictícios |
| GenAI | Ollama, opcional | Respostas abertas com contexto controlado |
| Segurança | Regras + roteamento local | Evitar dados inventados e recomendações indevidas |

## Estrutura

~~~text
mcduck-ai/
├── README.md
├── requirements.txt
├── data/
│   ├── historico_atendimento.csv
│   ├── perfil_investidor.json
│   ├── produtos_financeiros.json
│   └── transacoes.csv
├── docs/
│   ├── 01-documentacao-agente.md
│   ├── 02-base-conhecimento.md
│   ├── 03-prompts.md
│   ├── 04-metricas.md
│   └── 05-pitch.md
├── src/
│   ├── app.py
│   └── finance.py
└── tests/
    └── test_finance.py
~~~

## Como executar

### Pré-requisitos

- Python 3.10 ou superior;
- Ollama somente se quiser respostas abertas com LLM.

### Instalação

No terminal, a partir da raiz do projeto:

~~~powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
~~~

### Execução sem LLM

~~~powershell
streamlit run src/app.py
~~~

O painel, a análise de orçamento, o simulador e as perguntas estruturadas funcionam sem Ollama.

### Execução com Ollama

Em outro terminal:

~~~powershell
ollama pull gpt-oss
ollama serve
~~~

Depois execute o Streamlit. Para usar outro modelo ou endereço:

~~~powershell
$env:OLLAMA_MODEL = "nome-do-modelo"
$env:OLLAMA_URL = "http://localhost:11434/api/generate"
streamlit run src/app.py
~~~

## Testes

~~~powershell
python -m unittest discover -s tests -v
~~~

Os testes validam os totais do orçamento, a comparação de limites, o cálculo mensal da meta e o tratamento de prazo vencido.

## Segurança e privacidade

- A base distribuída com o projeto é totalmente fictícia;
- os cálculos críticos são determinísticos;
- a LLM recebe somente o contexto necessário;
- o agente recusa pedidos de senhas, tokens e dados de terceiros;
- informações ausentes são solicitadas, nunca presumidas;
- o catálogo de produtos financeiros da base original foi preservado por rastreabilidade, mas não é carregado pelo agente;
- nenhuma informação é enviada a uma API externa: quando habilitada, a LLM roda localmente via Ollama.

## Documentação

- [Definição, persona e arquitetura](docs/01-documentacao-agente.md)
- [Base de conhecimento](docs/02-base-conhecimento.md)
- [System prompt e cenários](docs/03-prompts.md)
- [Plano de avaliação](docs/04-metricas.md)
- [Roteiro do pitch](docs/05-pitch.md)

## Limitações

Este é um protótipo educacional. Ele não se conecta a contas bancárias, não persiste alterações feitas na interface, não calcula impostos ou juros e não presta consultoria financeira. Suas sugestões são possibilidades de organização que sempre devem ser avaliadas pelo usuário.
