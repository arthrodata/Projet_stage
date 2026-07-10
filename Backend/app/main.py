from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from Backend.app.routes.search import router
from Backend.app.routes.silene import router as silene_router
from Backend.app.routes.silene_expert import router as silene_expert_router
from Backend.app.routes.inaturalist import router as inaturalist_router
from Backend.app.routes.combined import router as combined_router
from Backend.app.routes.steli import router as steli_router
from Backend.app.routes.auth import router as auth_router
from Backend.app.routes.history import router as history_router
from Backend.app.routes.admin import router as admin_router
from Backend.app.utils.database import init_db
from pathlib import Path
import os


def _load_env_file() -> None:
    """
    Charge les variables depuis un fichier .env a la racine du projet.
    On evite d'ajouter une dependance (python-dotenv) pour garder le projet simple.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.exists():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value
    except OSError:
        return


_load_env_file()

app = FastAPI()


@app.on_event("startup")
def startup() -> None:
    init_db()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(silene_router)
app.include_router(silene_expert_router)
app.include_router(inaturalist_router)
app.include_router(combined_router)
app.include_router(steli_router)
app.include_router(auth_router)
app.include_router(history_router)
app.include_router(admin_router)
