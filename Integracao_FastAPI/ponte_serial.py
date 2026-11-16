
import json
import os
import time
import requests

# Enderecos utilizados na comunicacao entre Wokwi e FastAPI.
URL_SERIAL = os.getenv("BINOVA_SERIAL", "rfc2217://127.0.0.1:4000")
URL_API = os.getenv(
    "BINOVA_API", "http://127.0.0.1:8000/api/leituras?origem=wokwi_serial"
)


# Interpreta e valida os dados JSON recebidos do Arduino.
def interpretar_linha(linha: str):
    try:
        dado = json.loads(linha)
    except (ValueError, TypeError):
        return None

    if not isinstance(dado, dict):
        return None

    modo = dado.get("modo")

    if modo not in ("sensor", "manual") or type(dado.get("valida")) is not bool:
        return None

    valido = dado["valida"]

    if not valido:
        return {"valida": False, "modo": modo}

    nivel = dado.get("nivelPercentual")

    if type(nivel) is not int or not (0 <= nivel <= 100):
        return None

    if modo == "sensor":
        distancia = dado.get("distanciaCm")

        if type(distancia) not in (int, float) or not (2 <= distancia <= 400):
            return None

        return {
            "valida": True,
            "modo": "sensor",
            "distanciaCm": float(distancia),
            "nivelPercentual": nivel,
        }

    if "distanciaCm" in dado:
        return None

    return {
        "valida": True,
        "modo": "manual",
        "nivelPercentual": nivel
    }


# Envia a leitura validada para a FastAPI por uma requisicao HTTP POST.
def encaminhar(sessao: requests.Session, leitura: dict):
    resposta = sessao.post(URL_API, json=leitura, timeout=5)
    resposta.raise_for_status()
    return resposta.json()


# Mantem a conexao serial ativa e encaminha as leituras para a API.
def executar():
    try:
        import serial
    except ImportError:
        print("Instale as dependencias: py -m pip install -r requirements.txt")
        return

    print("BINOVA - Ponte Wokwi (Serial RFC2217) -> FastAPI (HTTP)")
    print("Porta Wokwi:", URL_SERIAL)
    print("API local:", URL_API)
    print("Aguardando simulador Wokwi no VS Code...")

    with requests.Session() as sessao:
        while True:
            try:
                with serial.serial_for_url(
                    URL_SERIAL,
                    baudrate=9600,
                    timeout=3
                ) as porta:

                    print("[CONECTADO] Serial do Wokwi aberta.")

                    while True:
                        conteudo = porta.readline().decode(
                            "utf-8",
                            errors="replace"
                        ).strip()

                        if not conteudo:
                            continue

                        leitura = interpretar_linha(conteudo)

                        if leitura is None:
                            continue

                        try:
                            registro = encaminhar(sessao, leitura)
                            pct = registro.get("nivelPercentual")

                            print(
                                f"[HTTP 201] modo={registro['modo']} "
                                f"nivel={str(pct) + '%' if pct is not None else '-'} "
                                f"situacao={registro['situacao']}"
                            )

                        except requests.RequestException as erro:
                            print(
                                "[ERRO HTTP] Inicie o servidor FastAPI. Detalhes:",
                                erro
                            )

            except (OSError, serial.SerialException) as erro:
                print("[AGUARDANDO WOKWI]", erro)
                time.sleep(3)


# Inicia a ponte serial e permite encerrar com Ctrl+C.
if __name__ == "__main__":
    try:
        executar()
    except KeyboardInterrupt:
        print("\nPonte encerrada")
