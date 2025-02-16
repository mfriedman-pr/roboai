import litellm
import ollama
import numpy as np

from shared.utils.model_server_client import _embed

from dotenv import load_dotenv
load_dotenv("shared/.env")  # take environment variables from .env.

import logging
log = logging.getLogger("llm_utils")
log.setLevel(logging.INFO)


def log_debug(msg):
    log.debug(msg)
    # print(msg)

def log_info(msg):
    log.info(msg)
    # print(msg)

async def get_embedding_sentence_transformers(text):
    log_debug(f"Getting sentence_transformer/HF embedding for text: {text}")
    response = await _embed(text)
    return response['embedding']

def get_embedding_ollama(text):
    log_debug(f"Getting ollama embedding for text: {text}")
    response = ollama.embeddings(
        model='mxbai-embed-large', 
        prompt=text
    )
    return response['embedding']

def get_embedding_litellm(text):
    log_debug(f"Getting litellm/HF embedding for text: {text}")
    response = litellm.embedding(
        model='huggingface/mixedbread-ai/mxbai-embed-large-v1', 
        input=[text]
    )
    log_debug(f"Embedding received: {response}")
    return response["data"][0]["embedding"]

async def get_embedding(text):
    log_debug(f"Getting embedding for text: {text}")
    return await get_embedding_sentence_transformers(text)

def cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    dot_product = np.dot(v1, v2)
    norm_v1 = np.linalg.norm(v1)
    norm_v2 = np.linalg.norm(v2)
    return dot_product / (norm_v1 * norm_v2)

async def get_closest_text(text: str, text_list: list[str], k: int = 1) -> str:
    log_info(f"Getting closest text for: '{text}' in list: {text_list}")
    query_vector = await get_embedding(text)
    log_debug(f"Query vector: {query_vector}")
    vectors = [await get_embedding(text) for text in text_list]
    similarities = [cosine_similarity(query_vector, vector) for vector in vectors]
    log_debug(f"Similarities: {similarities}")
    if k > 1:
        closest_indices = np.argsort(similarities)[-k:]
        return [text_list[i] for i in closest_indices]
    closest_index = np.argmax(similarities)
    return text_list[closest_index]
