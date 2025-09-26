import os
from copy import deepcopy
from typing import Iterable
from langchain.embeddings import init_embeddings
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from utils.enums import *
    
class Memory:
	EMBEDDING_MODEL = "openai:text-embedding-3-small"
	EMBEDDING_DIM = 1536
 

	def __init__(self):
		self.saver = None
		self.store = None
		self.embeddings = init_embeddings(
	  		self.EMBEDDING_MODEL,
			api_key=os.environ.get(SecretEnum.OPENAI_API_KEY.value)
		)
		self._setup_graph_memory()

	def _setup_graph_memory(self):
		"""
		Setup the memory for the graph builder.
		"""
		conn_string = os.environ.get(SecretEnum.POSTGRES_CONN_STRING.value)
		conn = Connection.connect(conn_string, autocommit=True)

		# Checkpointer
		self.saver = PostgresSaver(conn)
		self.saver.setup()

		# Store
		self.store = PostgresStore(
	  		conn,
			index={
				"dims": 1536,
				"embed": self.embeddings,
			}
		)

		self.store.setup()
  
DEFAULT_MEMORY = Memory()