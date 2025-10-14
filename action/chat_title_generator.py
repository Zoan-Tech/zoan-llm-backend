"""
Module for generating chat titles using LLM based on conversation history.
"""
import asyncio
import httpx
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

from config.logging import get_logger
from config import Config

logger = get_logger()

class ChatTitleGenerator:
    """Generates chat titles based on conversation history."""
    
    # Title generation prompt
    TITLE_GENERATION_PROMPT = """You are a helpful assistant that generates concise, descriptive titles for chat conversations.
Based on the conversation history provided, generate a short title (3-7 words) that captures the main topic or purpose of the user.

Rules:
- Keep it brief and descriptive
- Focus on the main topic or question
- Don't use quotes or special formatting
- Use title case
- Maximum 7 words

Respond with ONLY the title, nothing else."""

    def __init__(self):
        """Initialize the chat title generator with a lightweight model."""
        self.llm = ChatOpenAI(
            model="gpt-4.1-mini",  # Using a fast, cost-effective model for title generation
            temperature=0.7,
            max_tokens=20,
            api_key=Config.OPENAI_API_KEY,
        )
    
    def _count_conversation_turns(self, messages: list) -> int:
        """
        Count the number of conversation turns (user messages) in the history.
        
        Args:
            messages: List of message objects from the checkpoint
            
        Returns:
            Number of user turns in the conversation
        """
        if not messages:
            return 0
        
        turn_count = 0
        for message in messages:
            # Check if it's a user message (HumanMessage or role='user')
            if hasattr(message, '__class__'):
                message_type = message.__class__.__name__
                if message_type in ['HumanMessage', 'HumanMessageChunk']:
                    turn_count += 1
            elif isinstance(message, dict) and message.get('role') == 'user':
                turn_count += 1
        
        return turn_count
    
    def _extract_conversation_context(self, messages: list, max_messages: int = 6) -> str:
        """
        Extract conversation context for title generation.
        
        Args:
            messages: List of message objects from the checkpoint
            max_messages: Maximum number of messages to include
            
        Returns:
            Formatted conversation context string
        """
        if not messages:
            return ""
        
        context_parts = []
        message_count = 0
        
        for message in messages[:max_messages]:
            if message_count >= max_messages:
                break
                
            # Extract text content from message
            text_content = ""
            if hasattr(message, 'content'):
                if isinstance(message.content, str):
                    text_content = message.content
                elif isinstance(message.content, list):
                    # Handle list of content items
                    for item in message.content:
                        if isinstance(item, dict) and item.get('type') == 'text':
                            text_content += item.get('text', '')
                        elif isinstance(item, str):
                            text_content += item
            
            # Identify message type
            message_type = "unknown"
            if hasattr(message, '__class__'):
                class_name = message.__class__.__name__
                if 'Human' in class_name:
                    message_type = "User"
                elif 'AI' in class_name or 'Assistant' in class_name:
                    message_type = "Assistant"
            
            if text_content.strip():
                # Clean up any timestamp prefixes
                text_content = text_content.strip()
                if text_content.startswith('['):
                    # Remove timestamp like "[2025-10-14 12:34:56] - "
                    parts = text_content.split('] - ', 1)
                    if len(parts) > 1:
                        text_content = parts[1]
                
                context_parts.append(f"{message_type}: {text_content[:200]}")  # Limit each message to 200 chars
                message_count += 1
        
        return "\n".join(context_parts)
    
    async def generate_title(
        self,
        user_message: str,
        messages: list,
        conversation_id: str
    ) -> Optional[str]:
        """
        Generate a title for the conversation if conditions are met.
        
        Args:
            messages: List of message objects from the conversation history
            conversation_id: ID of the conversation
            
        Returns:
            Generated title string, or None if conditions not met or generation fails
        """
        try:
            # Count conversation turns
            turn_count = self._count_conversation_turns(messages)
            
            logger.debug(f"[ChatTitleGenerator] Conversation {conversation_id} has {turn_count} turns")
            
            # Only generate title if less than 4 turns
            if turn_count >= 4:
                logger.debug(f"[ChatTitleGenerator] Skipping title generation for {conversation_id} - {turn_count} turns (>= 4)")
                return None
            
            # Extract conversation context
            context = self._extract_conversation_context(messages)
            
            logger.debug(f"[ChatTitleGenerator] Generating title for {conversation_id}")
            
            # Generate title using LLM
            prompt_messages = [
                SystemMessage(content=self.TITLE_GENERATION_PROMPT),
                HumanMessage(content=f"Conversation:\n{context}"),
                HumanMessage(content=f"User's latest message: {user_message}"),
            ]
            
            # Use async invoke
            response = await self.llm.ainvoke(prompt_messages)
            title = response.content.strip()
            
            # Validate and clean the title
            if title:
                # Remove any quotes
                title = title.strip('"\'')
                # Limit length
                if len(title) > 100:
                    title = title[:97] + "..."
                
                logger.debug(f"[ChatTitleGenerator] Generated title for {conversation_id}: {title}")
                return title
            else:
                logger.warning(f"[ChatTitleGenerator] Empty title generated for {conversation_id}")
                return None
                
        except Exception as e:
            logger.error(f"[ChatTitleGenerator] Error generating title for {conversation_id}: {str(e)}")
            return None
    
    async def _call_update_title_webhook(
        self,
        conversation_id: str,
        title: str,
        auth_token: str = ""
    ) -> bool:
        """
        Call the webhook to update the chat title.
        
        Args:
            conversation_id: ID of the conversation (chatId)
            title: Generated title to update
            auth_token: Authorization token from the original request
            
        Returns:
            True if webhook call succeeded, False otherwise
        """
        try:
            webhook_url = f"{Config.WEBHOOK_URL}/api/webhooks/update-chat-title"
            
            # Use auth_token from request if available, otherwise fall back to webhook secret
            if auth_token:
                auth_header = f"{auth_token}"
            else:
                logger.warning(f"[ChatTitleGenerator] No auth token provided for webhook call for {conversation_id}")
                return False
            
            headers = {
                "Content-Type": "application/json",
                "Authorization": auth_header
            }
            
            payload = {
                "chatId": conversation_id,
                "title": title
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers=headers
                )
                
                if response.status_code == 200:
                    logger.info(f"[ChatTitleGenerator] Successfully updated title for {conversation_id} via webhook")
                    return True
                else:
                    logger.error(
                        f"[ChatTitleGenerator] Webhook failed for {conversation_id}: "
                        f"status={response.status_code}, body={response.text}"
                    )
                    return False
                    
        except httpx.TimeoutException:
            logger.error(f"[ChatTitleGenerator] Webhook timeout for {conversation_id}")
            return False
        except Exception as e:
            logger.error(f"[ChatTitleGenerator] Error calling webhook for {conversation_id}: {str(e)}")
            return False
    
    async def generate_and_update_title(
        self,
        user_message: str,
        messages: list,
        conversation_id: str,
        auth_token: str = ""
    ) -> bool:
        """
        Generate a title and update it via webhook.
        
        Args:
            messages: List of message objects from the conversation history
            conversation_id: ID of the conversation
            auth_token: Authorization token from the original request
            
        Returns:
            True if title was generated and webhook succeeded, False otherwise
        """
        try:
            # Generate the title
            title = await self.generate_title(user_message, messages, conversation_id)
            
            if not title:
                logger.debug(f"[ChatTitleGenerator] No title generated for {conversation_id}")
                return False
            
            # Call webhook to update the title with auth token
            success = await self._call_update_title_webhook(
                conversation_id, 
                title,
                auth_token=auth_token
            )
            
            return success
            
        except Exception as e:
            logger.error(f"[ChatTitleGenerator] Error in generate_and_update_title for {conversation_id}: {str(e)}")
            return False


# Singleton instance
chat_title_generator = ChatTitleGenerator()
