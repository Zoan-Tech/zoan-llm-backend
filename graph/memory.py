from langchain.embeddings import init_embeddings
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from utils.enums import *
from config import Config
    
class Memory:
	EMBEDDING_MODEL = "openai:text-embedding-3-small"
	EMBEDDING_DIM = 1536
 

	def __init__(self):
		self.saver = None
		self.store = None
		self.conn = None  # Store connection reference for cleanup
		self.embeddings = init_embeddings(
	  		self.EMBEDDING_MODEL,
			api_key=Config.OPENAI_API_KEY,
		)
		self._setup_graph_memory()

	def _setup_graph_memory(self):
		"""
		Setup the memory for the graph builder.
		"""
		conn_string = Config.POSTGRES_CONN_STRING
		 # Connection
		self.conn = Connection.connect(conn_string, autocommit=True)

		# Checkpointer
		self.saver = PostgresSaver(self.conn)
		self.saver.setup()

		# Store
		self.store = PostgresStore(
	  		self.conn,
			index={
				"dims": 1536,
				"embed": self.embeddings,
			}
		)

		self.store.setup()
  
memory = Memory()