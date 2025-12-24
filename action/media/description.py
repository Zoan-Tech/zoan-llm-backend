import base64
import httpx
from langchain.chat_models import init_chat_model
from langchain.messages import HumanMessage
import mimetypes
from model.media.description import (
    MediaDescriptionRequest,
    MediaDescriptionResponse,
)
from utils.const.multimodal import (
    IMAGE_MIME_TYPES
)
from config.logging import get_logger
logger = get_logger()

class Generator:
    def __init__(self, request: MediaDescriptionRequest):
        self.llm = init_chat_model(
            model=request.model,
        )
        
    def _process_batch_images(self, images: list[str]) -> list[MediaDescriptionResponse]:
        inputs = []
        for image_url in images:
            mimetype = mimetypes.guess_type(image_url)[0]
            image_data = base64.b64encode(httpx.get(image_url).content).decode("utf-8")
            inputs.append(
                [
                    HumanMessage(
                        content=[
                            {
                                "type": "text", 
                                "text": "Describe this image - {} in detail. Return the image description only.".format(image_url)
                            },
                            {
                                "type": "image",
                                "base64": image_data,
                                "mime_type": mimetype,
                            },
                        ]
                    )
                ]
            )

        results = self.llm.batch(inputs)
        responses = []
        for i, ai_msg in enumerate(results):
            media_desc = ""
            for content in ai_msg.content:
                if content['type'] == 'text':
                    media_desc += content['text'] + "\n"
                
            responses.append(
                MediaDescriptionResponse(
                    media=images[i],
                    description=media_desc.strip(),
                )
            )
        return responses
    
    def _process_batch_audio(self, audios: list[str]) -> list[MediaDescriptionResponse]:
        inputs = []
        for audio_url in audios:
            mimetype = mimetypes.guess_type(audio_url)[0]
            audio_data = base64.b64encode(httpx.get(audio_url).content).decode("utf-8")
            inputs.append(
                [
                    HumanMessage(
                        content=[
                            {
                                "type": "text", 
                                "text": "Describe this audio - {} in detail. Return the audio description only.".format(audio_url)
                            },
                            {
                                "type": "image",
                                "base64": audio_data,
                                "mime_type": mimetype,
                            },
                        ]
                    )
                ]
            )
            
        results = self.llm.batch(inputs)
        responses = []
        for i, ai_msg in enumerate(results):
            media_desc = ""
            for content in ai_msg.content:
                if content['type'] == 'text':
                    media_desc += content['text'] + "\n"
                
            responses.append(
                MediaDescriptionResponse(
                    media=audios[i],
                    description=media_desc.strip(),
                )
            )
        return responses

    def generate_media_info(self, medias: list[str]) -> list[MediaDescriptionResponse]:
        images = []
        audios = []
        # TODO: add more media types later
        
        for media in medias:
            if media.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp', '.tiff', '.svg')):
                images.append(media)
            
            elif media.lower().endswith(('.wav', '.mp3', '.aac', '.flac', '.ogg', '.m4a')):
                audios.append(media)
        
        media_responses = []  
        if images:
            images_response = self._process_batch_images(images)
            media_responses.extend(images_response)
        if audios:
            audios_response = self._process_batch_audio(audios)
            media_responses.extend(audios_response)
        return media_responses