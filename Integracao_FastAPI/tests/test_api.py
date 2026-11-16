"""Testes do recebimento e da validacao HTTP, sem fingir Wokwi conectado."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import app as api
from fastapi.testclient import TestClient
from ponte_serial import interpretar_linha

def test_fluxo_api(tmp_path, monkeypatch):
    monkeypatch.setattr(api, "ARQUIVO_DADOS", tmp_path / "leituras.jsonl")
    with api.TRAVA:
        api.HISTORICO.clear()
    cliente = TestClient(api.app)
    assert cliente.get("/api/saude").status_code == 200
    assert cliente.get("/").status_code == 200
    assert cliente.get("/api/leituras/ultima").status_code == 404

    for nivel, status in [(0, "DISPONIVEL"), (50, "ATENCAO"),
                          (75, "PROXIMO_DO_LIMITE"), (95, "CHEIO")]:
        entrada = {"valida": True, "modo": "sensor", "distanciaCm": 25.0 - 0.2 * nivel,
                   "nivelPercentual": nivel}
        r = cliente.post("/api/leituras?origem=teste_http", json=entrada)
        assert r.status_code == 201
        assert r.json()["situacao"] == status
        assert r.json()["origem"] == "teste_http"

    r = cliente.post("/api/leituras?origem=teste_http", json={
        "valida": True, "modo": "manual", "nivelPercentual": 83,
    })
    assert r.status_code == 201
    assert r.json()["distanciaCm"] is None
    assert r.json()["modo"] == "manual"
    assert cliente.get("/api/leituras/ultima").json()["nivelPercentual"] == 83
    assert len(cliente.get("/api/leituras").json()) == 5
    assert len((tmp_path / "leituras.jsonl").read_text(encoding="utf-8").splitlines()) == 5

    assert cliente.post("/api/leituras", json={
        "valida": True, "modo": "sensor", "nivelPercentual": 20,
    }).status_code == 422
    assert cliente.post("/api/leituras", json={
        "valida": True, "modo": "manual", "nivelPercentual": 101,
    }).status_code == 422
    assert cliente.post("/api/leituras", json={
        "valida": True, "modo": "manual", "nivelPercentual": 50,
        "distanciaCm": 15.0,
    }).status_code == 422
    assert cliente.post("/api/leituras", json={
        "valida": False, "modo": "sensor",
    }).status_code == 201
    assert cliente.get("/api/leituras/ultima").json()["situacao"] == "SEM_DADOS"

def test_parser_da_porta_serial():
    assert interpretar_linha('{"distanciaCm":15.0,"nivelPercentual":50,"valida":true,"modo":"sensor"}') == {
        "distanciaCm": 15.0, "nivelPercentual": 50, "valida": True, "modo": "sensor"
    }
    assert interpretar_linha('{"nivelPercentual":95,"valida":true,"modo":"manual"}') == {
        "nivelPercentual": 95, "valida": True, "modo": "manual"
    }
    assert interpretar_linha('BINOVA INICIANDO') is None
    assert interpretar_linha('{"valida":false,"modo":"sensor"}') == {
        "valida": False, "modo": "sensor"
    }
    assert interpretar_linha('{"modo":"sensor","valida":true,"nivelPercentual":10}') is None
