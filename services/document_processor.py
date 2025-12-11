from typing import List, Optional
from config.logging import get_logger
from utils.model import Model
from services.qdrant_messages_client import qdrant_messages_client
from docling.document_converter import DocumentConverter
from docling_core.transforms.chunker.hybrid_chunker import HybridChunker
from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
from transformers import AutoTokenizer
from utils.const.multimodal import EMBEDDING_MODEL_ID
from utils.http_client import safe_http_get

logger = get_logger()

# Initialize embedding model
TEXT_EMBEDDING_MODEL = Model.openai_text_embedding_3_small

tokenizer = HuggingFaceTokenizer(
    tokenizer=AutoTokenizer.from_pretrained(EMBEDDING_MODEL_ID),
)
chunker = HybridChunker(tokenizer=tokenizer)
converter = DocumentConverter()


class DocumentProcessor:
    """Service for processing documents and storing in Qdrant messages collection"""
    
    @staticmethod
    def process_and_store_document(
        attachment_url: str,
        user_id: str,
        conversation_id: str,
        mime_type: str = "application/pdf"
    ) -> bool:
        """
        Process a document from URL, chunk it, and store in Qdrant.
        
        Args:
            attachment_url: URL of the document
            user_id: User ID
            conversation_id: Conversation ID
            mime_type: MIME type of the document
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Validate and download document
            logger.info(f"Processing document from {attachment_url}")
            document_content = safe_http_get(attachment_url)
            if document_content is None:
                logger.error(f"Failed to download document from {attachment_url}")
                return False
            
            # Convert document
            result = converter.convert(document_content)
            
            # Chunk the document
            chunk_iter = chunker.chunk(dl_doc=result.document)
            chunks = list(chunk_iter)
            
            if not chunks:
                logger.warning(f"No chunks extracted from document {attachment_url}")
                return False
            
            # Create embeddings and prepare data
            processed_chunks = []
            for chunk in chunks:
                chunk_text = chunk.text
                if not chunk_text.strip():
                    continue
                    
                # Generate embedding
                embedding = TEXT_EMBEDDING_MODEL.embed_query(chunk_text)
                
                processed_chunks.append({
                    "text": chunk_text,
                    "vector": embedding,
                })
            
            # Store in Qdrant
            success = qdrant_messages_client.store_document_chunks(
                user_id=user_id,
                conversation_id=conversation_id,
                attachment_url=attachment_url,
                chunks=processed_chunks,
            )
            
            if success:
                logger.info(f"Successfully stored {len(processed_chunks)} chunks for {attachment_url}")
            else:
                logger.error(f"Failed to store chunks for {attachment_url}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error processing document {attachment_url}: {str(e)}")
            return False
    
    @staticmethod
    def search_relevant_content(
        query: str,
        user_id: str,
        conversation_id: str,
        limit: int = 5,
        score_threshold: float = 0.7,
    ) -> str:
        """
        Search for relevant document content based on query.
        
        Args:
            query: Search query
            user_id: User ID
            conversation_id: Conversation ID
            limit: Maximum number of chunks to retrieve
            score_threshold: Minimum similarity score
            
        Returns:
            Formatted string with relevant document content
        """
        try:
            # Generate query embedding
            query_vector = TEXT_EMBEDDING_MODEL.embed_query(query)
            
            # Search in Qdrant
            chunks = qdrant_messages_client.search_relevant_chunks(
                query_vector=query_vector,
                user_id=user_id,
                conversation_id=conversation_id,
                limit=limit,
                score_threshold=score_threshold,
            )
            
            if not chunks:
                return ""
            
            # Format results
            formatted_content = "Relevant content from uploaded documents:\n\n"
            for i, chunk in enumerate(chunks, 1):
                formatted_content += f"[{i}] (Score: {chunk['score']:.3f})\n{chunk['text']}\n\n"
            
            return formatted_content
            
        except Exception as e:
            logger.error(f"Error searching relevant content: {str(e)}")
            return ""


document_processor = DocumentProcessor()
