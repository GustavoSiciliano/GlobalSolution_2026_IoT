"""Binova: API HTTP local para receber leituras do Arduino simulado no Wokwi."""

import json
import math
import threading
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, field_validator, model_validator

PASTA = Path(__file__).resolve().parent
ARQUIVO_DADOS = PASTA / "dados" / "leituras.jsonl"
HISTORICO = deque(maxlen=200)
TRAVA = threading.Lock()

class LeituraEntrada(BaseModel):
    """Mesmo formato do JSON gerado em sketch.ino."""
    model_config = ConfigDict(extra="forbid", strict=True)
    valida: bool
    modo: Literal["sensor", "manual"]
    distanciaCm: float | None = None
    nivelPercentual: int | None = None

    @field_validator("distanciaCm")
    @classmethod
    def validar_distancia(cls, v):
        if v is not None and (not math.isfinite(v) or not 2 <= v <= 400):
            raise ValueError("A distancia deve estar entre 2 e 400 cm")
        return v

    @model_validator(mode="after")
    def validar_combinacao(self):
        if self.valida:
            if self.nivelPercentual is None or not 0 <= self.nivelPercentual <= 100:
                raise ValueError("Uma leitura valida exige percentual entre 0 e 100")
            if self.modo == "sensor" and self.distanciaCm is None:
                raise ValueError("O modo sensor exige distanciaCm")
            if self.modo == "manual" and self.distanciaCm is not None:
                raise ValueError("O modo manual nao deve conter distanciaCm")
        elif self.nivelPercentual is not None or self.distanciaCm is not None:
            raise ValueError("Leitura invalida nao deve conter distancia ou percentual")
        return self

def situacao(nivel: int | None, valida: bool) -> str:
    """Classificacao usada no LCD e nos LEDs."""
    if not valida or nivel is None:
        return "SEM_DADOS"
    if nivel < 50:
        return "DISPONIVEL"
    if nivel < 75:
        return "ATENCAO"
    if nivel < 95:
        return "PROXIMO_DO_LIMITE"
    return "CHEIO"

def carregar_historico():
    """Carrega no maximo as ultimas 200 leituras validas do arquivo local."""
    if not ARQUIVO_DADOS.exists():
        return
    with ARQUIVO_DADOS.open(encoding="utf-8") as arq:
        for linha in arq:
            try:
                dado = json.loads(linha)
                if isinstance(dado, dict):
                    HISTORICO.append(dado)
            except ValueError:
                continue

carregar_historico()

app = FastAPI(
    title="Binova | Integração Wokwi + FastAPI",
    description="Recebimento HTTP dos dados UART do Arduino Uno por uma ponte Python local.",
    version="1.0.0",
)

@app.get("/", include_in_schema=False)
def painel():
    return FileResponse(PASTA / "static" / "index.html")

@app.get("/api/saude")
def saude():
    """Confirma que a API esta respondendo."""
    return {"servico": "binova-fastapi", "status": "online"}

@app.post("/api/leituras", status_code=201)
def registrar(
    leitura: LeituraEntrada,
    origem: Literal["wokwi_serial", "teste_http"] = Query(default="teste_http"),
):
    """Recebe uma leitura validada e registra o resultado com sua origem."""
    registro = {
        "recebidoEm": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "origem": origem,
        "modo": leitura.modo,
        "valida": leitura.valida,
        "distanciaCm": leitura.distanciaCm,
        "nivelPercentual": leitura.nivelPercentual,
        "situacao": situacao(leitura.nivelPercentual, leitura.valida),
    }
    with TRAVA:
        ARQUIVO_DADOS.parent.mkdir(parents=True, exist_ok=True)
        with ARQUIVO_DADOS.open("a", encoding="utf-8") as arq:
            arq.write(json.dumps(registro, ensure_ascii=False) + "\n")
        HISTORICO.append(registro)
    return registro

@app.get("/api/leituras/ultima")
def ultima():
    """Consulta a ultima leitura recebida pela API."""
    with TRAVA:
        if not HISTORICO:
            raise HTTPException(status_code=404, detail="Nenhuma leitura recebida")
        return HISTORICO[-1]

@app.get("/api/leituras")
def listar(limite: int = Query(default=20, ge=1, le=200)):
    """Lista as ultimas leituras, com limite configuravel."""
    with TRAVA:
        return list(HISTORICO)[-limite:][::-1]
