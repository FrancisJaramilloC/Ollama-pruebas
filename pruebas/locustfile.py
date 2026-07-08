import random
import json
from locust import HttpUser, task, between


class RecetasUser(HttpUser):
    wait_time = between(30, 60)

    RECETAS = [
        "incorporar 2 tazas de harina",
        "mezclar 3 huevos con una taza de azucar",
        "incorporar 500 gramos de harina y mezclar 10 minutos",
        "licuar 3 bananitas y mezclar 2 minutos",
        "asar 15 minutos a 180 grados",
        "incorporar 2 tazas de azucar y 3 huevos",
        "batir 4 claras a punto de nieve e incorporar 1 taza de azucar",
        "hornear 30 minutos y dejar reposar 10 minutos",
        "incorporar una pizca de sal y mezclar 2 minutos",
        "incorporar 1 cucharada de sal y mezclar 5 minutos",
    ]

    def on_start(self):
        pass

    @task
    def analizar_receta(self):
        receta = random.choice(self.RECETAS)
        payload = {"source": receta}
        with self.client.post(
            "/analyze",
            json=payload,
            headers={"Content-Type": "application/json"},
            catch_response=True,
            name="POST /analyze"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")

    @task(1)
    def health_check(self):
        self.client.get("/health")
