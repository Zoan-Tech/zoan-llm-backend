from langchain.agents.middleware import SummarizationMiddleware
from utils.model import Model

def get_base_middleware(
    max_tokens_before_summary=10000,
    messages_to_keep=10,
) -> list:
    base_middleware = [
        SummarizationMiddleware(
            model=Model.openai_gpt_5_mini,
            trigger=[
                ('tokens', max_tokens_before_summary),
            ],
            keep=(
                'messages', messages_to_keep
            )
        ),
    ]
    
    return base_middleware