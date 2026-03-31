import os
import sys
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).parent.parent / "eap-core"))

from eap.parser import EthiopianAddressParser

parser: EthiopianAddressParser | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global parser
    data_dir = os.getenv("DATA_DIR", str(Path(__file__).parent.parent / "eap-core"))
    parser = EthiopianAddressParser(
        data_dir=data_dir,
        use_transformer_ner=False,
        use_semantic_search=False,
    )
    parser.load()
    yield
    parser = None


app = FastAPI(title="SAP Service", version="1.0.0", lifespan=lifespan)


@app.exception_handler(Exception)
async def error_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "code": "INTERNAL_SERVER_ERROR"},
    )


class ParseRequest(BaseModel):
    address: str = Field(..., min_length=2, max_length=500)


class Candidate(BaseModel):
    name: str
    score: float
    method: str
    lat: float
    lng: float
    subcity: str


class ParseResponse(BaseModel):
    subcity: str | None
    woreda: str | None
    landmark: str | None
    landmark_amharic: str | None
    category: str | None
    latitude: float | None
    longitude: float | None
    confidence: float
    match_score: float
    match_method: str
    script: str
    candidates: list[Candidate]


class AutocompleteRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=200)


class AutocompleteItem(BaseModel):
    name: str
    amharic: str
    subcity: str
    category: str
    lat: float
    lng: float
    score: float


class AutocompleteResponse(BaseModel):
    results: list[AutocompleteItem]
    query_time_ms: float


@app.post("/api/v1/addresses/parse", response_model=ParseResponse)
async def parse_address(req: ParseRequest):
    if not req.address.strip():
        return JSONResponse(
            status_code=400,
            content={"error": "address cannot be empty", "code": "BAD_REQUEST"},
        )

    result = parser.parse(req.address)

    candidates = [
        Candidate(
            name=c.landmark.name,
            score=round(c.score, 1),
            method=c.method,
            lat=c.landmark.lat,
            lng=c.landmark.lng,
            subcity=c.landmark.subcity or "",
        )
        for c in result.candidates
    ]

    return ParseResponse(
        subcity=result.subcity,
        woreda=result.woreda,
        landmark=result.landmark_name,
        landmark_amharic=result.landmark_amharic,
        category=result.landmark_category,
        latitude=result.latitude,
        longitude=result.longitude,
        confidence=result.confidence,
        match_score=result.landmark_match_score,
        match_method=result.landmark_match_method,
        script=result.script,
        candidates=candidates,
    )


@app.post("/api/v1/addresses/autocomplete", response_model=AutocompleteResponse)
async def autocomplete(req: AutocompleteRequest):
    start = time.perf_counter()
    matches = parser.landmark_index.match(req.query, top_k=5, threshold=40.0)

    results = [
        AutocompleteItem(
            name=m.landmark.name,
            amharic=m.landmark.amharic,
            subcity=m.landmark.subcity or "",
            category=m.landmark.category or "",
            lat=m.landmark.lat,
            lng=m.landmark.lng,
            score=round(m.score, 1),
        )
        for m in matches
    ]

    elapsed = (time.perf_counter() - start) * 1000
    return AutocompleteResponse(results=results, query_time_ms=round(elapsed, 2))


@app.get("/api/v1/addresses/health")
async def health():
    count = len(parser.landmark_index.landmarks) if parser else 0
    return {"status": "ok" if parser else "loading", "landmarks_loaded": count}
