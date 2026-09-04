# Base de Conhecimento

## Dados utilizados

Todos os registros representam um cliente fictício e existem apenas para demonstrar o protótipo.

| Arquivo | Formato | Uso no McDuck AI |
|---|---|---|
| historico_atendimento.csv | CSV | Contextualiza temas já tratados sem armazenar conversas completas |
| perfil_investidor.json | JSON | Fornece valores iniciais de renda, reserva e limites para o modelo |
| transacoes.csv | CSV | Calcula receitas, despesas e totais por categoria |
| produtos_financeiros.json | JSON | Preservado da base original, mas deliberadamente não carregado |

Embora o nome perfil_investidor.json tenha sido mantido para respeitar a estrutura original do laboratório, o conteúdo foi adaptado à organização financeira. O arquivo não é usado para recomendar investimentos.

## Adaptações realizadas

- As transações foram atualizadas para um mês fictício completo;
- as despesas receberam categorias compatíveis com orçamento pessoal;
- o perfil passou a incluir limites mensais;
- as metas deixaram de ser pré-carregadas e agora são criadas pelo próprio usuário na interface;
- o histórico foi reescrito com temas de orçamento, gastos, reserva e metas;
- o catálogo de produtos não foi alterado nem conectado à aplicação.

## Estratégia de integração

### Carregamento

No primeiro uso, src/finance.py lê a base inicial e src/database.py cria data/mcduck.db. Depois disso, renda, categorias, tipos de gasto, metas, aportes, histórico do chat e registro de alterações são lidos do SQLite.

~~~python
BASE_DIR = Path(__file__).resolve().parents[1]
profile, transactions, history = load_knowledge(BASE_DIR)
~~~

A conexão é aberta apenas durante cada operação, confirmada e fechada em seguida. O recurso do banco é armazenado no cache do Streamlit, mas os dados permanecem no arquivo SQLite depois que o aplicativo é encerrado. Nenhuma chave de API ou dado bancário é necessário.

### Uso dos dados

O fluxo separa cálculo e geração de linguagem:

1. **SQLite:** mantém o estado financeiro atual e o histórico;
2. **Python:** soma valores, agrupa categorias, calcula percentuais e metas;
3. **motor de ações:** executa alterações explícitas solicitadas no chat;
4. **roteamento local:** responde solicitações estruturadas, dados sensíveis e temas proibidos;
5. **LLM local:** recebe apenas um resumo para perguntas abertas;
6. **interface:** apresenta e permite editar os valores persistidos.

Essa divisão impede que a LLM seja a fonte dos números críticos.

## Regras de cálculo

### Orçamento

~~~text
total de receitas = soma das transações do tipo entrada
total de despesas = soma das transações do tipo saída
valor disponível = total de receitas - total de despesas
percentual comprometido = total de despesas / total de receitas × 100
~~~

### Meta financeira

~~~text
valor faltante = máximo(0, valor da meta - valor já guardado)
economia mensal = valor faltante / meses restantes
~~~

O resultado mensal é arredondado para cima no centavo. O cálculo não presume juros, rentabilidade ou inflação. Se o prazo estiver vencido, o agente pede uma nova data.

## Exemplo de contexto calculado

Com os arquivos distribuídos no projeto:

~~~text
CLIENTE FICTÍCIO
Nome: João Silva
Renda registrada: R$ 5.000,00
Objetivo principal: completar a reserva de emergência

ORÇAMENTO DE 2026-08
Receitas: R$ 5.000,00
Despesas: R$ 2.788,90
Disponível: R$ 2.211,10
Renda comprometida: 55,8%

GASTOS POR CATEGORIA
Moradia: R$ 1.480,00
Alimentação: R$ 570,00
Transporte: R$ 295,00
Educação: R$ 200,00
Saúde: R$ 188,00
Lazer: R$ 55,90
~~~

## Qualidade e governança dos dados

- **Validação de formato:** valores são convertidos para número e prazos seguem AAAA-MM;
- **minimização:** somente campos necessários entram no contexto da LLM;
- **privacidade:** a base é fictícia e não contém credenciais;
- **rastreabilidade:** os arquivos utilizados e as regras de cálculo estão documentados neste projeto;
- **consistência:** os testes verificam os cálculos mais sensíveis;
- **atualização:** novos registros podem ser adicionados aos arquivos mantendo os mesmos campos.

## Dados que o usuário precisa informar

Para usar um cenário próprio, o usuário deve substituir ou ajustar:

- renda líquida do período;
- despesas com categoria, valor e tipo;
- limites desejados por categoria;
- nome, valor total, valor acumulado e prazo de cada meta.

Se algum desses dados faltar, o agente deve sinalizar a ausência em vez de completar o valor por conta própria.
