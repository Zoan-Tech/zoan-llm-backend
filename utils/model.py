from sentence_transformers import SentenceTransformer

class Model:
    clip_ViT_B_32 = SentenceTransformer("clip-ViT-B-32")  # 512-d embeddings