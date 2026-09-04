# Pitch do McDuck AI — 3 minutos

## Estrutura

| Tempo | Seção | Apoio visual |
|---|---|---|
| 0:00–0:30 | Problema | Tela inicial |
| 0:30–1:20 | Solução | Visão geral |
| 1:20–2:20 | Demonstração | Painel, chat e meta |
| 2:20–3:00 | Diferencial e impacto | Arquitetura e encerramento |

## Roteiro falado

### 1. Problema — 30 segundos

> “Olá! Este é o McDuck AI, meu projeto final do Bootcamp Bradesco de Dados, GenAI e Cybersecurity da DIO.
>
> Muitas pessoas sabem quanto recebem, mas têm dificuldade para visualizar quanto da renda já está comprometido, quais categorias mais pesam e quanto precisam guardar para alcançar um objetivo. Quando essas informações ficam espalhadas, planejar o mês e tomar decisões conscientes se torna muito mais difícil.”

### 2. Solução — 50 segundos

> “O McDuck AI é um agente de organização financeira pessoal. Ele reúne renda, despesas, limites e metas e transforma esses dados em uma visão simples do orçamento.
>
> O agente soma receitas e despesas, agrupa os gastos por categoria, mostra o percentual da renda comprometida e compara cada categoria com um limite definido. Para uma meta, ele calcula o valor que falta e quanto precisa ser separado por mês dentro do prazo.
>
> Os dados ficam salvos localmente em SQLite, então o planejamento continua disponível ao reabrir o aplicativo. O foco é orçamento, controle de gastos e metas: ele não ensina nem recomenda investimentos e não promete retornos. A palavra Investimentos pode ser usada apenas como uma categoria definida pelo usuário.”

### 3. Demonstração — 60 segundos

> “Nesta demonstração usamos dados fictícios. No painel, a receita é de R$ 5 mil, as despesas somam R$ 2.788,90 e o valor disponível é de R$ 2.211,10. Moradia aparece como a maior categoria, com R$ 1.480.
>
> Na barra lateral eu posso ajustar renda e gastos e ver os indicadores serem recalculados imediatamente.
>
> No chat, posso consultar o orçamento ou pedir mudanças: ‘Adicione R$ 300 em Pets’, ‘Minha renda passou para R$ 6 mil’ ou ‘Reorganize minha renda’. O agente aplica comandos explícitos, salva as mudanças e pergunta quando falta uma decisão do usuário. Se eu pedir conteúdo ou recomendação de investimento, ele recusa; ainda assim, aceita Investimentos como simples categoria de planejamento.
>
> No simulador, informo o valor da meta, quanto já tenho e o prazo. O sistema calcula quanto guardar por mês e avisa se esse valor supera o disponível atual.”

### 4. Diferencial e impacto — 40 segundos

> “O principal diferencial é separar inteligência generativa de cálculo financeiro. Somas, percentuais, limites e metas são calculados por funções Python testadas; a LLM local é usada somente para perguntas abertas. Assim, o modelo não é responsável por inventar ou calcular números críticos.
>
> O projeto também aplica minimização de dados, registra alterações, persiste o planejamento em SQLite, recusa informações sensíveis e funciona nos recursos essenciais mesmo quando o Ollama está desligado.
>
> Com isso, o McDuck AI torna a organização financeira mais clara, prática e segura. Ele não decide pelo usuário: entrega contexto para que cada pessoa tome decisões mais conscientes. Obrigado!”

## Sequência da demonstração

1. Abra a aba **Visão geral** e destaque os quatro indicadores;
2. altere o gasto de Lazer acima do limite e mostre o alerta;
3. peça no chat: “Adicione R$ 300 em Pets” e mostre a atualização do painel;
4. peça: “Coloque todo o saldo disponível em Investimentos” e explique a separação de escopo;
5. pergunte: “Qual criptomoeda devo comprar?” para demonstrar a proteção;
6. encerre criando uma meta na aba **Suas metas** e reabrindo o app para mostrar a persistência.

## Checklist de gravação

- [ ] Duração entre 2:40 e 3:00;
- [ ] fonte da interface legível;
- [ ] dados fictícios mencionados;
- [ ] problema e público-alvo claros;
- [ ] cálculo de orçamento demonstrado;
- [ ] proteção contra recomendação demonstrada;
- [ ] diferencial técnico explicado;
- [ ] áudio sem ruído e cursor visível.

## Link do vídeo

Adicionar após a gravação: **[link pendente]**
