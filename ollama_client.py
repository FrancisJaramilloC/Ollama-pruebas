import requests


class OllamaClient:

    def __init__(
        self,
        model: str = "llama3.2:3b",
        host: str = "http://localhost:11434/api/generate",
        timeout: int = 300
    ) -> None:
        self.model = model
        self.host = host
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        response = requests.post(
            self.host,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                "options": {
                    "temperature": 0.0,
                    "num_predict": 256
                }
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()["response"]
