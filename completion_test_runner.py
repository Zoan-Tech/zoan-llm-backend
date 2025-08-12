from dotenv import load_dotenv
load_dotenv()

from langgraph.graph.state import CompiledStateGraph
import os
from model import CompletionRequest
from action.completion import CompletionAction
from utils.enums import SecretEnum
import asyncio

message = "Hello, how can you help me today?"
# message = "I want to create a simple flappy bird game. Can you help me with that?"

payload = {
    "user_id": "101ab125-996c-4476-97d1-77e84f342f80",
    "conversation_id": "41fe8a46-3415-4b45-a7bd-d9d343604183", 
    "message": message,
    "agents": [
        {
            "name": "primary_agent",
            "description": "Primary Agent",
            "instruction": "You are a helpful assistant.",
            "model": "gpt-4.1-mini",
            "api_key": os.environ.get(SecretEnum.OPENAI_SECRET_KEY.value),
            "model_kwargs": {
                "temperature": 0.5,
                "max_tokens": 500
            },
            "stream_usage": True,
            "workflows": []
        },
        {
            "name": "game_generator",
            "description": "Generates a game based on user input.",
            "instruction": "You are a game generator agent.",
            "model": "gpt-4.1-mini",
            "api_key": os.environ.get(SecretEnum.OPENAI_SECRET_KEY.value),
            "model_kwargs": {
                "temperature": 0.7,
                "max_tokens": 1000
            },
            "stream_usage": True,
            "workflows": [
                {
                    "name": "2d_game_generator",
                    "description": "Generates a 2D game based on user input.",
                    "steps": [
                        {
                            "name": "Human Input",
                            "description": "Say hello to the user",

                            "type": "builtin",
                            "args": {
                                "message": "Hello, how can I help you with your game today?"
                            },
                            "response_mapping": {
                                "human_input": "game_specification"
                            }
                        },
                        {
                            "name": "human_input",
                            "description": "game specification",
                        }
                    ]
                }
            ]
        }
    ]
}

completion_request = CompletionRequest.model_validate(payload)

completion_action = CompletionAction()

agents = completion_request.agents
# compiled_graph = completion_action.graph_cache.get_or_store_compiled_graph(
#     agents, 
#     lambda agents: completion_action.graph_builder.build_graph(agents)
# )
# compiled_graph.get_graph().draw_png("graph.png")

completion = completion_action.create_completion(
    user_id=completion_request.user_id,
    conversation_id=completion_request.conversation_id,
    message=completion_request.message,
    agents=agents,
)

async def main():
    async for step in completion:
        print(step)

asyncio.run(main())
