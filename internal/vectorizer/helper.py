import base64
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
import mimetypes

from utils.model import Model
from config.logging import get_logger
logger = get_logger()

MAX_TOKENS = 200
class MediaInfoGenerator:
    def __init__(self, model: str = Model.openai_gpt_5_mini, max_tokens: int = MAX_TOKENS, **kwargs):
        self.llm = init_chat_model(
            model=model,
            max_tokens=max_tokens,
            **kwargs
        )

    def generate_media_info(self, image_name: str, image_data) -> str:
        try:
            mimetype = mimetypes.guess_type(image_name)[0]
            image_data = base64.b64encode(image_data).decode("utf-8")
            system_message = SystemMessage(
                content=(
                    "You are an expert at analyzing visual media content. Your task is to describe images in detail, focusing on objects, style, and visual characteristics. Provide comprehensive descriptions that capture both the content and artistic style of the media.\n"
                    "Sample Response Format:\n"
                    "Description: [detailed description of the image content, objects, style, colors, and any notable features] - 'Silver pixel-art spaceship, top-down'\n",
                    "Objects: [list of main objects in the image] - 'spaceship, stars, planets'\n"
                    "Style: [artistic style of the image] - 'pixel art, retro video game'"
                    "Keep the response concise but informative."
                )
            )
            message = HumanMessage(
                content=[
                    {"type": "text", "text": "Describe the content of the media - {} in detail.".format(image_name)},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mimetype};base64,{image_data}"},
                    },
                ]
            )
            ai_msg = self.llm.invoke([system_message, message])
            return ai_msg.content
        except Exception as e:
            logger.error(f"Failed to generate image info: {e}")
            return "{}".format(image_name)
        
media_info_generator = MediaInfoGenerator()