from langchain_core.prompts import PromptTemplate

zoan_system_prompt = """
<<default system prompt>>
You are an AI game/dApp generator assistant, operate under the Zoan framework.
Your task is to help users create engaging and interactive game/dApp by invoking to generator modules when the conditions are met.
<<default system prompt>>
"""
    

system_prompt = PromptTemplate.from_template("""
{system_prompt}

<<owner's specifications>>
{description}
{prompt}
<<owner's specifications>>
""")
    