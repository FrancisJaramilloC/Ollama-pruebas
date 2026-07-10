"""
Cliente HTTP para interactuar con la API local de Ollama.
Permite enviar prompts a un modelo de lenguaje (como llama3.2:3b)
y recibir la respuesta generada de forma síncrona.
"""
import requests

class OllamaClient:
    """
    Clase cliente que encapsula las peticiones HTTP hacia el servicio de Ollama.
    """
    def __init__(
        self,
        model: str = "llama3.2:3b",
        host: str = "http://localhost:11434/api/generate",
        timeout: int = 300
    ) -> None:
        """
        Inicializa la configuración del cliente Ollama.

        :param model: Nombre del modelo a utilizar en Ollama.
        :param host: URL del endpoint para la generación de texto.
        :param timeout: Tiempo máximo de espera en segundos para la respuesta.
        """
        self.model = model
        self.host = host
        self.timeout = timeout

    def generate(self, prompt: str) -> str:
        """
        Envía un prompt a Ollama y retorna el texto de la respuesta generada.

        :param prompt: Texto de entrada para el LLM.
        :return: Respuesta de texto plano generada por el LLM.
        """
        response = requests.post(
            self.host,
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False,
                # Temperatura en 0.0 para maximizar determinismo y consistencia en el parseo
                "options": {
                    "temperature": 0.0,
                    "num_predict": 256
                }
            },
            timeout=self.timeout
        )
        response.raise_for_status()
        return response.json()["response"]

