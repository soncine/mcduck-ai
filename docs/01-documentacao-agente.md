# Documentação do Agente

## Caso de uso

### Problema

Muitas pessoas conhecem sua renda, mas não conseguem visualizar quanto está comprometido, quais categorias pesam mais e quanto precisam reservar mensalmente para realizar um objetivo. Sem essa visão, decisões do dia a dia ficam desconectadas das metas de médio e longo prazo.

### Solução

O **McDuck AI** recebe renda, despesas, limites e metas, organiza os valores e devolve uma análise simples e verificável. O agente destaca excessos, simula o esforço mensal necessário para cada meta e indica uma próxima ação possível. Ele informa quando faltam dados e não toma decisões pelo usuário.

### Público-alvo

Pessoas iniciantes em organização financeira pessoal que desejam montar um orçamento, controlar gastos e planejar metas sem depender de planilhas complexas.

### Escopo funcional

1. Consolidar receitas e despesas;
2. agrupar gastos por categoria;
3. calcular renda comprometida e saldo disponível;
4. comparar gastos com limites definidos;
5. calcular economia mensal para uma meta;
6. avaliar a compatibilidade da meta com o orçamento atual;
7. sugerir possibilidades de ajuste sem julgamento.

## Persona e tom de voz

### Nome

**McDuck AI**

### Personalidade

- Organizado, cuidadoso e consultivo;
- amigável sem infantilizar o usuário;
- objetivo, transparente e não julgador;
- curioso diante de dados ausentes;
- prudente em temas que ultrapassam seu escopo.

### Tom de comunicação

Português do Brasil simples e acessível. Respostas curtas, com valores em Real, cálculo explicado e uma próxima ação prática quando houver base suficiente.

### Exemplos de linguagem

- **Saudação:** “Olá! Sou o McDuck AI. Posso organizar seu orçamento, analisar gastos ou planejar uma meta. Por onde começamos?”
- **Confirmação:** “Com os valores informados, suas despesas representam 55,8% da renda.”
- **Dado ausente:** “Para calcular essa meta, ainda preciso do valor total, do que você já guardou e do prazo.”
- **Limitação:** “Não recomendo investimentos específicos. Posso ajudar a descobrir quanto cabe no seu orçamento para uma meta.”
- **Próxima ação:** “Revise primeiro a maior categoria e escolha um limite que faça sentido para sua realidade.”

## Arquitetura

~~~mermaid
flowchart TD
    A[Usuário] --> B[Streamlit]
    B --> C{Tipo de solicitação}
    C -->|Orçamento ou meta| D[Motor Python determinístico]
    C -->|Pergunta aberta| E[Ollama local]
    F[(JSON e CSV fictícios)] --> D
    F --> G[Contexto mínimo]
    G --> E
    D --> H[Validação e formatação]
    E --> H
    H --> I[Resposta ao usuário]
~~~

### Componentes

| Componente | Descrição |
|---|---|
| Interface | Streamlit com painel, gráficos Plotly, chat, orçamento editável e metas do usuário |
| Motor de cálculos | finance.py soma valores, compara limites e calcula metas |
| LLM | Ollama local para perguntas abertas; configuração por variáveis de ambiente |
| Base de conhecimento | JSON e CSV fictícios na pasta data |
| Roteamento | Perguntas críticas são respondidas localmente antes de acionar a LLM |
| Validação | Regras de escopo, privacidade, dados ausentes e anti-alucinação |

### Fluxo de uma solicitação

1. A interface recebe a mensagem e os valores da sessão;
2. o classificador simples verifica se é orçamento, meta, dado sensível, investimento ou assunto fora do escopo;
3. cálculos financeiros são executados em Python;
4. somente perguntas abertas seguem para o Ollama com contexto mínimo;
5. a resposta mostra resultado, explicação e próxima ação.

## Segurança e anti-alucinação

### Estratégias adotadas

- [x] Usar somente valores fornecidos ou presentes nos arquivos fictícios;
- [x] executar somas, percentuais e metas por código, não por texto generativo;
- [x] informar explicitamente quando algum dado necessário estiver ausente;
- [x] restringir o contexto enviado à LLM;
- [x] recusar pedidos de credenciais e informações de terceiros;
- [x] bloquear recomendações de investimentos e promessas de retorno;
- [x] manter os dados locais por meio do Ollama;
- [x] mostrar que os dados da demonstração são fictícios;
- [x] cobrir cálculos centrais com testes automatizados.

### Dados mínimos por operação

| Operação | Dados obrigatórios |
|---|---|
| Orçamento | Renda e despesas |
| Comparação de limites | Categoria, gasto e limite definido |
| Meta | Nome, valor total, valor já guardado e prazo |
| Sugestão de ajuste | Gastos categorizados e objetivo do usuário |

### Limitações declaradas

O McDuck AI:

- não acessa contas bancárias nem movimenta dinheiro;
- não solicita senhas, tokens, número completo de cartão ou credenciais;
- não recomenda produtos ou investimentos;
- não prevê rentabilidade, inflação ou cenário econômico;
- não calcula impostos, encargos de dívida ou juros compostos;
- não substitui profissional financeiro, contador ou advogado;
- não mantém as alterações da interface após o fim da sessão;
- não responde assuntos fora de organização financeira pessoal.

## Decisões de projeto

O catálogo produtos_financeiros.json foi preservado porque faz parte da base original do laboratório, mas não é carregado pela aplicação. Essa separação mantém a rastreabilidade do material e respeita o escopo definido: organização financeira, não recomendação de investimentos.
