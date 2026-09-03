# Aplicação

## Arquivos

- app.py: interface Streamlit e integração opcional com Ollama;
- finance.py: carregamento de dados, cálculos e respostas locais seguras.

## Executar

A partir da raiz do projeto:

~~~powershell
python -m pip install -r requirements.txt
streamlit run src/app.py
~~~

O modelo padrão é gpt-oss no Ollama. Para trocar:

~~~powershell
$env:OLLAMA_MODEL = "nome-do-modelo"
~~~

Sem Ollama, o painel, o simulador e as respostas estruturadas continuam disponíveis.
