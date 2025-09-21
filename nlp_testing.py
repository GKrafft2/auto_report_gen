from transformers import AutoTokenizer, AutoModelForCausalLM
import time

class Apertus8b():
    def __init__(self):        
        model_id = "swiss-ai/Apertus-8B-Instruct-2509"
        self.tokenizer = AutoTokenizer.from_pretrained(model_id)

        # max_memory = {0: "7.5GiB", "cpu": "32GiB"} # when plugged in
        max_memory = {"cpu": "32GiB"} # when running on battery

        self.model = AutoModelForCausalLM.from_pretrained(
            model_id,
            torch_dtype="auto",
            device_map="auto",
            max_memory=max_memory,
            offload_folder="offload_cache"
        )

    def send_prompt(self,prompt: str):

        messages_think = [
            {"role": "user", "content": prompt}
        ]

        text = self.tokenizer.apply_chat_template(
            messages_think,
            tokenize=False,
            add_generation_prompt=True,
        )
        model_inputs = self.tokenizer([text], return_tensors="pt", add_special_tokens=False).to(self.model.device)

        # Generate the output
        start = time.time()
        generated_ids = self.model.generate(**model_inputs, max_new_tokens=200)
        end = time.time()

        new_tokens = generated_ids.shape[1] - model_inputs["input_ids"].shape[1]

        print(f"estimated tokens per second = {new_tokens/(end-start):0.2f}")

        # Get and decode the output
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]) :]
        
        return self.tokenizer.decode(output_ids, skip_special_tokens=True)


