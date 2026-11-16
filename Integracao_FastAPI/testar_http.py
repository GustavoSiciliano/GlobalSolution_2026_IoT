
import time
import requests

URL = "http://127.0.0.1:8000/api/leituras?origem=teste_http"

EXEMPLOS = [
    {"valida": True, "modo": "sensor", "distanciaCm": 25.0, "nivelPercentual": 0},
    {"valida": True, "modo": "sensor", "distanciaCm": 15.0, "nivelPercentual": 50},
    {"valida": True, "modo": "manual", "nivelPercentual": 95},
]

# Testa o recebimento de leituras pela FastAPI usando dados simulados.
def testar_api():
    for leitura in EXEMPLOS:
        try:
            resposta = requests.post(URL, json=leitura, timeout=5)
            resposta.raise_for_status()

            print("[TESTE HTTP]", resposta.status_code, resposta.json()["situacao"])

        except requests.RequestException as erro:
            print("Falha ao chamar a API:", erro)
            break

        time.sleep(1)


if __name__ == "__main__":
    testar_api()
