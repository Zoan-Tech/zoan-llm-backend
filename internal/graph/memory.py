from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from utils.enums import *
from config import Config
from config.logging import get_logger
from utils.model import Model

logger = get_logger()

class Memory:
	def __init__(self):
		self.saver = None
		self.store = None
		self.embeddings = Model.openai_text_embedding_3_small
		self._setup_graph_memory()

	def _setup_graph_memory(self):
		"""
		Setup the memory for the graph builder.
		Uses PostgresSaver and PostgresStore with built-in connection pooling for thread-safe concurrent access.
		Automatically runs database migrations/schema setup on initialization.
		The setup() method is idempotent - safe to call multiple times.
		"""
		conn_string = Config.POSTGRES_CONN_STRING
  
		try:
			# Initialize PostgresSaver
			self.saver_cm = PostgresSaver.from_conn_string(conn_string)
			self.saver = self.saver_cm.__enter__()
			# Setup database schema and run migrations (idempotent)
			self.saver.setup()
			logger.info("[Memory] PostgresSaver schema setup completed")
		except Exception as e:
			logger.error(f"[Memory] Failed to setup PostgresSaver: {str(e)}")
			raise
  
		try:
			# Initialize PostgresStore
			self.store_cm = PostgresStore.from_conn_string(
				conn_string,
				index={
					"dims": 1536,
					"embed": self.embeddings,
				}
			)
			self.store = self.store_cm.__enter__()
			# Setup database schema and run migrations (idempotent)
			self.store.setup()
			logger.info("[Memory] PostgresStore schema setup completed")
		except Exception as e:
			logger.error(f"[Memory] Failed to setup PostgresStore: {str(e)}")
			# Cleanup saver if store setup fails
			if hasattr(self, 'saver_cm') and getattr(self, 'saver', None) is not None:
				try:
					self.saver_cm.__exit__(None, None, None)
				except Exception:
					pass
			raise
		
		logger.info("[Memory] Memory system initialized with thread-safe connection pooling")
	
	def close(self):
		"""Close the savers gracefully."""
		logger.info("[Memory] Closing PostgresSaver and PostgresStore")
		if hasattr(self, 'saver_cm') and getattr(self, 'saver', None) is not None:
			self.saver_cm.__exit__(None, None, None)
		if hasattr(self, 'store_cm') and getattr(self, 'store', None) is not None:
			self.store_cm.__exit__(None, None, None)

memory = Memory()