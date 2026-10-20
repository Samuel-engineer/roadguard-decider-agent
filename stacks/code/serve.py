import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response, status
import torch
import logging
logger = logging.getLogger()

from strands_decider.infer import SystemOneEngine
from strands_decider.modeling import StrandsDeciderModel
from strands_decider.schema import SystemOneRequest

# Variable globale stockant le moteur en mémoire
engine: SystemOneEngine | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Équivalent direct de model_fn : exécuté une seule fois au boot."""
    global engine
    HF_TOKEN = os.getenv("HF_TOKEN")
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model_id = os.getenv("MODEL_ID", "StrandsAgents/strands-decider-2B-hobson-v21")
    logger.info(model_id)

    print(f"Chargement du modèle sur {device} depuis {model_id}...")
    model = StrandsDeciderModel.load(model_id)

    if hasattr(model.torso, "merge_and_unload"):
        model.torso = model.torso.merge_and_unload()
        logger.info("model passe torso fusion")
    
    engine = SystemOneEngine(model)
    print("Moteur SystemOneEngine prêt à servir.")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/ping")
def ping():
    """Health check SageMaker : renvoie 200 quand le moteur est initialisé."""
    if engine is None:
        return Response(
            content="Modèle en cours de chargement",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    return Response(content="OK", status_code=status.HTTP_200_OK)


@app.post("/invocations")
async def invocations(request: Request):
    """Combine input_fn, predict_fn et output_fn."""
    if engine is None:
        return Response(
            content="Modèle non prêt",
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )

    # 1. Équivalent input_fn
    content_type = request.headers.get("content-type", "")
    if "application/json" not in content_type:
        return Response(
            content=f"Unsupported content type: {content_type}",
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        )

    body_bytes = await request.body()
    try:
        input_data = SystemOneRequest.model_validate_json(body_bytes)
    except Exception as exc:
        return Response(
            content=f"Erreur de validation JSON: {exc}",
            status_code=status.HTTP_400_BAD_REQUEST,
        )

    # 2. Équivalent predict_fn
    with torch.no_grad():
        prediction = engine.evaluate(input_data)

    # 3. Équivalent output_fn
    return Response(
        content=prediction.model_dump_json(),
        media_type="application/json",
        status_code=status.HTTP_200_OK,
    )