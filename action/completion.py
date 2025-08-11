import os, json
from langchain.chat_models import init_chat_model
from langgraph.prebuilt import create_react_agent
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.store.postgres import PostgresStore
from psycopg import Connection
from config.prompt_template import system_prompt, zoan_system_prompt
from utils.helper import decrypt_token

from utils.enums import *

class CompletionAction:
    """Handles completion actions using LangGraph and a Postgres database."""
    
    def __init__(self):
        conn_string = os.environ.get(SecretEnum.POSTGRES_CONN_STRING.value)
        conn = Connection.connect(conn_string, autocommit=True)

        self.store = PostgresStore(conn)
        self.store.setup()
        
        self.saver = PostgresSaver(conn)
        self.saver.setup()

    async def create_completion(
        self,
        user_id: str,
        conversation_id: str,
        description: str,
        prompt: str,
        message: str,
        model: str,
        model_token: str,
        response_format: dict,
        model_kwargs: dict,
        **kwargs
    ):
        """
        Create a completion using the specified model and messages.
        
        :param model_name: The name of the model to use for completion.
        :param messages: A list of messages to send to the model.
        :param kwargs: Additional keyword arguments for the chat model.
        :return: The response from the chat model.
        """
        
        api_key = None        
        try:
            api_key = decrypt_token(model_token, os.environ.get(SecretEnum.FERNET_SECRET.value))
        except Exception as e:
            api_key = None
            
        llm = init_chat_model(
            model=model,
            stream_usage=True,
            api_key=api_key,
            **model_kwargs
        )
        
        prompt = system_prompt.format(
            system_prompt=zoan_system_prompt,
            description=description,
            prompt=prompt,
        )
        
        agent_executor = create_react_agent(
            llm,
            prompt=prompt,
            checkpointer=self.saver,
            store=self.store,
            tools=[],
            response_format=response_format,
        )
        
        
        input = {
            "messages": [
                ("system", "You are a helpful assistant."),
                ("user", f"Answer this question: {message}")
            ]
        }
        config = {
            "configurable": {
                "user_id": user_id,
                "thread_id": conversation_id,
            },
            "recursion_limit": 100,
        }
        try:
            for chunk, _ in agent_executor.stream(input, config=config, stream_mode="messages"):
                yield json.dumps(chunk.model_dump(), ensure_ascii=False)
        except Exception as e:
            yield json.dumps({"content": str(e)}, ensure_ascii=False)
    
completion_action = CompletionAction()