"""
Module for updating chat titles via webhook.
"""
import requests

from config.logging import get_logger
from config import Config

logger = get_logger()


def update_title(
    conversation_id: str,
    title: str,
    auth_token: str = ""
) -> bool:
    """
    Call the webhook to update the chat title.
    
    Args:
        conversation_id: ID of the conversation (chatId)
        title: Title to update
        auth_token: Authorization token from the original request
        
    Returns:
        True if webhook call succeeded, False otherwise
    """
    try:
        webhook_url = f"{Config.WEBHOOK_URL}/api/webhooks/update-chat-title"
        
        # Use auth_token from request if available
        if not auth_token:
            logger.warning(f"[ChatTitleGenerator] No auth token provided for webhook call for {conversation_id}")
            return False
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": auth_token
        }
        
        payload = {
            "chatId": conversation_id,
            "title": title
        }
        
        response = requests.post(
            webhook_url,
            json=payload,
            headers=headers,
            timeout=10.0
        )
        
        if response.status_code == 200:
            logger.info(f"[ChatTitleGenerator] Successfully updated title for {conversation_id} to '{title}'")
            return True
        else:
            logger.error(
                f"[ChatTitleGenerator] Webhook failed for {conversation_id}: "
                f"status={response.status_code}, body={response.text}"
            )
            return False
            
    except requests.exceptions.Timeout:
        logger.error(f"[ChatTitleGenerator] Webhook timeout for {conversation_id}")
        return False
    except Exception as e:
        logger.error(f"[ChatTitleGenerator] Error calling webhook for {conversation_id}: {str(e)}")
        return False

