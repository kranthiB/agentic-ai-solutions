# kubernetes_agent/utils/embedding_client.py

import yaml

# Imports for various providers
from typing import List

# HuggingFace
from sentence_transformers import SentenceTransformer

# OpenAI
import openai

# Azure OpenAI
import openai as azure_openai

# Google Vertex AI - if needed (optional)

class EmbeddingClient:
    """Flexible Embedding Client supporting HuggingFace, OpenAI, Azure, Google etc."""

    def __init__(self, config_path="configs/embedding_config.yaml"):
        with open(config_path, "r") as f:
            config = yaml.safe_load(f)

        embedding_cfg = config["embedding"]
        self.provider = embedding_cfg.get("provider", "huggingface").lower()

        # HuggingFace
        if self.provider == "huggingface":
            self.model = SentenceTransformer(embedding_cfg["huggingface_model"])

        # OpenAI
        elif self.provider == "openai":
            self.openai_model = embedding_cfg["openai_model"]

        # Azure OpenAI
        elif self.provider == "azure":
            self.azure_endpoint = embedding_cfg["azure_endpoint"]
            self.azure_api_key = embedding_cfg["azure_api_key"]
            self.azure_deployment_name = embedding_cfg["azure_deployment_name"]
            azure_openai.api_type = "azure"
            azure_openai.api_base = self.azure_endpoint
            azure_openai.api_key = self.azure_api_key
            azure_openai.api_version = "2023-05-15"

        # Google Gemini (Vertex AI Embeddings) — optional for future
        elif self.provider == "google":
            self.google_model = embedding_cfg["google_model"]
            # TODO: Add Vertex AI integration if needed

        else:
            raise ValueError(f"Unsupported embedding provider: {self.provider}")

    async def generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector from input text.

        Args:
            text (str): Input string to embed.

        Returns:
            List[float]: Embedding vector.
        """
        if self.provider == "huggingface":
            return self.model.encode(text).tolist()

        elif self.provider == "openai":
            response = openai.Embedding.create(
                input=[text],
                model=self.openai_model
            )
            return response['data'][0]['embedding']

        elif self.provider == "azure":
            response = azure_openai.Embedding.create(
                input=[text],
                deployment_id=self.azure_deployment_name
            )
            return response['data'][0]['embedding']

        elif self.provider == "google":
            # Placeholder: implement Vertex AI Embedding API call
            raise NotImplementedError("Google Gemini Embedding not implemented yet.")

        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
