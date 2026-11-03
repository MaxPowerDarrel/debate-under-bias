"""Make one small API call to each configured model."""
import anthropic
import yaml
from dotenv import load_dotenv

load_dotenv()
config = yaml.safe_load(open("configs/pilot.yaml"))
client = anthropic.Anthropic()

for role, model in config["models"].items():
    reply = client.messages.create(
        model=model,
        max_tokens=20,
        messages=[{"role": "user", "content": "Reply with the single word: ready"}],
    )
    text = next((b.text for b in reply.content if b.type == "text"), "")
    print(f"{role}: {model} -> {text.strip()}")
