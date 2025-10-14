from langchain.embeddings import init_embeddings
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg_pool import ConnectionPool
from utils.enums import *
from config import Config
from config.logging import get_logger

logger = get_logger()

class Memory:
	EMBEDDING_MODEL = "openai:text-embedding-3-small"
	EMBEDDING_DIM = 1536
 
	# Connection pool configuration
	POOL_MIN_SIZE = 5
	POOL_MAX_SIZE = 20
	POOL_TIMEOUT = 30.0
	POOL_MAX_IDLE = 300.0  # 5 minutes
	POOL_MAX_LIFETIME = 3600.0  # 1 hour

	def __init__(self):
		self.saver = None
		self.store = None
		self.pool = None  # Connection pool for thread-safe concurrent access
		self.embeddings = init_embeddings(
	  		self.EMBEDDING_MODEL,
			api_key=Config.OPENAI_API_KEY,
		)
		self._setup_graph_memory()

	def _setup_graph_memory(self):
		"""
		Setup the memory for the graph builder with connection pooling.
		Connection pool enables thread-safe concurrent access from multiple requests.
		"""
		conn_string = Config.POSTGRES_CONN_STRING
		
		# Create connection pool for concurrent access
		logger.info(f"[Memory] Creating PostgreSQL connection pool (min={self.POOL_MIN_SIZE}, max={self.POOL_MAX_SIZE})")
		self.pool = ConnectionPool(
			conninfo=conn_string,
			min_size=self.POOL_MIN_SIZE,
			max_size=self.POOL_MAX_SIZE,
			timeout=self.POOL_TIMEOUT,
			max_idle=self.POOL_MAX_IDLE,
			max_lifetime=self.POOL_MAX_LIFETIME,
			# Configure pool behavior
			kwargs={
				"autocommit": True,
			}
		)

		# Setup PostgresSaver - it will use connections from pool internally
		# Note: PostgresSaver manages its own connection acquisition from the sync_connection
		with self.pool.connection() as setup_conn:
			# Initialize saver with a connection from the pool
			# PostgresSaver will handle its own connection management
			temp_saver = PostgresSaver(setup_conn)
			temp_saver.setup()
			logger.info("[Memory] PostgresSaver schema initialized")

			# Initialize store
			temp_store = PostgresStore(
				setup_conn,
				index={
					"dims": self.EMBEDDING_DIM,
					"embed": self.embeddings,
				}
			)
			temp_store.setup()
			logger.info("[Memory] PostgresStore schema initialized")
		
		# Create a connection string-based saver that will create connections as needed
		# This allows PostgresSaver to work with the pool via connection string
		self.saver = PostgresSaver.from_conn_string(conn_string)
		
		# Note: PostgresStore doesn't have from_conn_string, so we keep it None
		# If store is needed, implement a wrapper that gets connections from pool
		self.store = None
		
		logger.info("[Memory] Memory system initialized with connection pool")
	
	def close(self):
		"""Close the connection pool gracefully."""
		if self.pool:
			logger.info("[Memory] Closing PostgreSQL connection pool")
			self.pool.close()
  
memory = Memory()