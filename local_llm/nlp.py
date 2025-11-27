import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from transformers import AutoTokenizer, AutoModelForCausalLM
import time
import torch
from llama_cpp import Llama
from urllib.request import urlretrieve
import os
from pathlib import Path
from huggingface_hub import hf_hub_download


class Apertus8b:
    def __init__(self):
        model_id = "swiss-ai/Apertus-8B-Instruct-2509"
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # max_memory = {0: "7.5GiB", "cpu": "32GiB"} # when plugged in
        max_memory = {"cpu": "32GiB"}  # when running on battery

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            device_map="auto",
            max_memory=max_memory,
            offload_folder="offload_cache",
        )

    def send_prompt(self, prompt: str):

        messages_think = [{"role": "user", "content": prompt}]

        text = self.tokenizer.apply_chat_template(
            messages_think,
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = self.tokenizer(
            [text], return_tensors="pt", add_special_tokens=False
        ).to(self.model.device)

        # Generate the output
        start = time.time()
        generated_ids = self.model.generate(**model_inputs, max_new_tokens=200)
        end = time.time()

        new_tokens = generated_ids.shape[1] - model_inputs["input_ids"].shape[1]

        logger.info(f"estimated tokens per second = {new_tokens/(end-start):0.2f}")

        # Get and decode the output
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]) :]

        return self.tokenizer.decode(output_ids, skip_special_tokens=True)


class Apertus8bgguf_llamcpp(Apertus8b):
    def __init__(self):

        model_path = hf_hub_download(
            "DevQuasar/swiss-ai.Apertus-8B-Instruct-2509-GGUF",
            "swiss-ai.Apertus-8B-Instruct-2509.Q8_0.gguf",
        )

        self.model = Llama(
            model_path=model_path,
            n_ctx=65536,  # adjust
            n_gpu_layers=-1,  # >0 to offload layers to GPU if compiled with CUDA/Metal
        )

    def send_prompt(self, prompt: str):

        response = self.model(
            "What are the benefits of renewable energy?",
            max_tokens=100,  # Maximum number of tokens to generate
            temperature=0.7,  # Creativity level
        )

        return response["choices"][0]["text"]


class Apertus8bgguf_transformers(Apertus8b):
    def __init__(self):

        model_id = "DevQuasar/swiss-ai.Apertus-8B-Instruct-2509-GGUF"
        filename = "swiss-ai.Apertus-8B-Instruct-2509.Q8_0.gguf"

        self.tokenizer = AutoTokenizer.from_pretrained(model_id, gguf_file=filename)
        self.model = AutoModelForCausalLM.from_pretrained(model_id, gguf_file=filename)


class llama318bbgguf_llamcpp(Apertus8b):
    def __init__(self):

        model_path = hf_hub_download(
            "bartowski/Meta-Llama-3.1-8B-Instruct-GGUF",
            "Meta-Llama-3.1-8B-Instruct-Q8_0.gguf",
        )

        self.model = Llama(
            model_path=model_path,
            n_ctx=131072,  # adjust
            n_gpu_layers=-1,  # >0 to offload layers to GPU if compiled with CUDA/Metal
        )

    def send_prompt(self, prompt: str):

        response = self.model(
            "What are the benefits of renewable energy?",
            max_tokens=100,  # Maximum number of tokens to generate
            temperature=0.7,  # Creativity level
        )

        return response["choices"][0]["text"]
