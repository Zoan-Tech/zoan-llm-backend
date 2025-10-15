from langchain.embeddings import init_embeddings
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from utils.enums import *
from config import Config
from config.logging import get_logger

logger = get_logger()

class Memory:
	EMBEDDING_MODEL = "openai:text-embedding-3-small"
	EMBEDDING_DIM = 1536

	def __init__(self):
		self.saver = None
		self.store = None
		self.embeddings = init_embeddings(
	  		self.EMBEDDING_MODEL,
			api_key=Config.OPENAI_API_KEY,
		)
		self._setup_graph_memory()

	def _setup_graph_memory(self):
		"""
		Setup the memory for the graph builder.
		Uses PostgresSaver and PostgresStore with built-in connection pooling for thread-safe concurrent access.
		"""
		conn_string = Config.POSTGRES_CONN_STRING
  
		self.saver_cm = PostgresSaver.from_conn_string(conn_string)
		self.saver = self.saver_cm.__enter__()
  
		self.store_cm = PostgresStore.from_conn_string(
			conn_string,
			index={
				"dims": 1536,
				"embed": self.embeddings,
			}
		)
		self.store = self.store_cm.__enter__()
		
		logger.info("[Memory] Memory system initialized with thread-safe connection pooling")
	
	def close(self):
		"""Close the savers gracefully."""
		logger.info("[Memory] Closing PostgresSaver and PostgresStore")
		if hasattr(self, 'saver_cm') and self.saver:
			self.saver_cm.__exit__(None, None, None)
		if hasattr(self, 'store_cm') and self.store:
			self.store_cm.__exit__(None, None, None)

memory = Memory()