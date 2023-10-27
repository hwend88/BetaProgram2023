# @id zj8Xa2goK3H0b0gQzJDcCM
import json
import re
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain.prompts.chat import (
    AIMessagePromptTemplate,
    ChatPromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
)

'imports' # Python blocks do not support returning langchain classes yet

# @id I7Q4dfmKyAe2wj5j3eBHA8
def on_copilot_message(chat_id, chat, env):
  # 1. Retrieve environment
  key = env['preferences']['secret|openai:key']
  tables = env['tablesSummary']
  question = chat[-1]['message']

  # 2. Instantiate LLM
  llm = ChatOpenAI(temperature=0.2, openai_api_key=key, model_name='gpt-4')

  # 3. Run the LLM to translate the user question into an SQL query
  query_prompts = [PROMPT_QUERY, '{question}']
  query_context = {'tables': tables, 'question':question}
  query = ask_llm(llm, query_prompts, query_context)

  # 4. If the LLM answer does not look like an SQL query, we stop here
  if not query.startswith('SELECT'):
    return { 'message': query }

  # 5. Execute the SQL query on DuckDB
  rows = []
  try:
    rows = execute_query(query, env)
  except Exception as err:
    return { 'message': f'Unfortunately, query execution failed.\n\n&nbsp;\n\n{err}\n\n&nbsp;\n\n```\n{query}\n```' }

  # 6. Run the LLM to transform the resulting rows into a textural reply
  reply_prompts = [PROMPT_REPLY]
  reply_context = {'rows': rows, 'question':question}
  reply = ask_llm(llm, reply_prompts, reply_context)

  # 7. Postprocess the answer
  # Replace quotes around table names with STOIC backticks
  query = re.sub(r'"([^"/]+?/[^"/]+?)"', r'`\1`', query)

  # Remove trailing semicolon from query
  if query.endswith(';'):
    query = query[:-1]

  # Create action to open a new pipeline
  action = { 'type': 'createPipelineFromSQLQuery', 'query': query }

  # Return the result payload
  return { 'message': reply, 'explanation': f'```\n{query}\n```', 'action': action }

# @id rvJcM9VmYj0ANx2hYIhNsh
def ask_llm(llm, strings, context):
  """
  Converts an array of strings into a LangChain prompt.

  The first string will always be the system message, and then the
  other strings will be alternatively user and assistant messages.
  """

  prompts = []
  prompts.append(SystemMessagePromptTemplate.from_template(strings[0]))

  role = 'user'

  for string in strings[1:]:
    if role == 'user':
      prompts.append(HumanMessagePromptTemplate.from_template(string))
      role = 'assistant'
    else:
      prompts.append(AIMessagePromptTemplate.from_template(string))
      role = 'user'

  prompt = ChatPromptTemplate.from_messages(prompts)
  messages = prompt.format_prompt(**context).to_messages()

  print_messages(messages)

  return llm(messages).content

# @id n2ge0XWz2b1PKi1Ymbcsku
def execute_query(query, env):
  """
  Executes an SQL query on the DuckDB database.

  Replaces occurrences of table references (backtick names) with their actual identifier.
  """

  for table_def in env['tables']:
    query = query.replace(table_def['ref'], table_def['id'])
  rows = db.query(query).fetchmany(10)
  return json.dumps(rows, indent = 2)

# @id QYiyMqNrpmlXkp2EZjzmAt
def print_messages(messages):
  """
  Simple helper to print a list of OpenAI messages to the console.
  """

  for msg in messages:
    print('>>>>')
    print(msg.content)

# @id u2wedKEnS7ZVxX7zRZ7lJz
PROMPT_QUERY = '''
  You are a database expert, specialized in generating SQL queries to answer questions.

  If an SQL query is not appropriate to answer the question, just reply directly to the question.
  If you can generate an SQL query, respond with only the query, without anything else.

  Try to include interesting columns in the query. For instance, if user asks "What is the brand
  with the most sales", you would include the brand name as result, but also the total number of
  sales, for context. This is just an example, add as much context as possible.

  When you add a new column to a query, name it with a friendly name, starting with a capital,
  between double quotes. This name will be shown to users, so it should not be too technical.

  When the query requires an aggregation like MAX, MIN, etc., do not forget to add a GROUP BY
  clause in the query.

  Do not limit the query to the first result. Try to include at least 10 rows in the result, so
  the user will see more context.

  The DuckDB database contains these tables:
  {tables}
  '''

# @id GJautonvSebvWF8x1DmOR5
PROMPT_REPLY = '''
  You are a helpful assistant that tries to answer user questions based on a database content.

  The user question was: {question}

  The database result is:
  {rows}

  Formulate a textural response to the question, based on the database result.
  Use markdown to emphasize values.
  '''