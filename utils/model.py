from sentence_transformers import SentenceTransformer
from langchain.embeddings import init_embeddings

class Model:
    clip_ViT_B_32 = SentenceTransformer("clip-ViT-B-32")  # 512-d embeddings
    openai_text_embedding_3_small = init_embeddings(
        "openai:text-embedding-3-small"
    )  # 1536-d embeddings
    
    all_MinLM_L6_v2 = SentenceTransformer("all-MiniLM-L6-v2")  # 384-d embeddings
    
    openai_gpt_5_mini = "openai:gpt-5-mini"  # lightweight GPT-5 model