"""
DICOM volume service.

    POST /api/volume/load          {"path": "<folder under DICOM_DATA_ROOT>", ...} -> volume_id + metadata
    GET  /api/volume/{id}/meta     metadata (dims, spacing, value range, warnings)
    GET  /api/volume/{id}/raw      little-endian int16 voxels in Unity texture order (x fastest)
    GET  /api/volumes              loaded volumes
    GET  /api/health

Run:  uvicorn app.main:app --host 127.0.0.1 --port 8000
Only metadata derived from geometry is ever returned; no patient fields leave this service.
"""
from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .dicom_loader import SeriesError, load_series
from .volume import pack_for_unity, resample

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dicom_service")

DATA_ROOT = Path(os.environ.get("DICOM_DATA_ROOT", "./data")).resolve()

app = FastAPI(title="DICOM Volume Service", version="0.1.0")
_cache: dict[str, tuple[bytes, dict]] = {}


class LoadRequest(BaseModel):
    path: str = Field(..., description="Folder containing one DICOM series, relative to DICOM_DATA_ROOT")
    series_uid: str | None = Field(None, description="Pick a specific SeriesInstanceUID (default: largest)")
    target_spacing_mm: float | None = Field(None, gt=0, description="Resample to isotropic spacing, e.g. 1.0")
    max_dim: int = Field(512, ge=16, le=2048, description="Cap on the largest texture dimension")


def _resolve_folder(rel: str) -> Path:
    p = (DATA_ROOT / rel).resolve()
    if p != DATA_ROOT and DATA_ROOT not in p.parents:
        raise HTTPException(400, "path must stay inside DICOM_DATA_ROOT")
    if not p.is_dir():
        raise HTTPException(404, f"folder not found: {rel}")
    return p


@app.get("/api/health")
def health():
    return {"status": "ok", "data_root": str(DATA_ROOT), "loaded": len(_cache)}


@app.post("/api/volume/load")
def load_volume(req: LoadRequest):
    folder = _resolve_folder(req.path)
    key = hashlib.sha1(
        f"{folder}|{req.series_uid}|{req.target_spacing_mm}|{req.max_dim}".encode()
    ).hexdigest()[:12]

    if key not in _cache:
        try:
            vol = load_series(folder, series_uid=req.series_uid)
        except SeriesError as e:
            raise HTTPException(422, str(e)) from e
        vol = resample(vol, req.target_spacing_mm, req.max_dim)
        _cache[key] = pack_for_unity(vol)
        log.info("Cached volume %s (%.1f MB)", key, _cache[key][0].__len__() / 1e6)

    _, meta = _cache[key]
    return {"volume_id": key, **meta}


@app.get("/api/volumes")
def list_volumes():
    return [{"volume_id": k, "dims": [m["dim_x"], m["dim_y"], m["dim_z"]]} for k, (_, m) in _cache.items()]


@app.get("/api/volume/{volume_id}/meta")
def volume_meta(volume_id: str):
    if volume_id not in _cache:
        raise HTTPException(404, "unknown volume_id; call /api/volume/load first")
    return {"volume_id": volume_id, **_cache[volume_id][1]}


@app.get("/api/volume/{volume_id}/raw")
def volume_raw(volume_id: str):
    if volume_id not in _cache:
        raise HTTPException(404, "unknown volume_id; call /api/volume/load first")
    raw, meta = _cache[volume_id]
    headers = {
        "X-Dim-X": str(meta["dim_x"]),
        "X-Dim-Y": str(meta["dim_y"]),
        "X-Dim-Z": str(meta["dim_z"]),
        "X-Spacing-MM": ",".join(f"{v:.6f}" for v in meta["spacing_mm"]),
        "X-Format": "int16-le",
    }
    return Response(content=raw, media_type="application/octet-stream", headers=headers)
