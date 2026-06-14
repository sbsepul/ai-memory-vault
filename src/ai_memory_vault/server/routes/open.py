"""Open a local path in the OS file manager.

Security: only paths under $HOME are allowed; symlinks are resolved before
the check so a crafted path cannot escape the home directory.
"""
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ...config import HOME

router = APIRouter(prefix="/api/open", tags=["open"])


class OpenRequest(BaseModel):
    path: str  # relative to HOME, e.g. "repos/my-project"


@router.post("")
def open_path(req: OpenRequest):
    # Reject obvious traversal attempts early
    if ".." in req.path or req.path.startswith("/"):
        raise HTTPException(status_code=400, detail="Invalid path")

    target = (HOME / req.path).resolve()

    # Resolved path must still be under HOME
    try:
        target.relative_to(HOME.resolve())
    except ValueError:
        raise HTTPException(status_code=403, detail="Path outside home directory")

    if not target.exists():
        raise HTTPException(status_code=404, detail="Path does not exist on disk")

    if sys.platform == "darwin":
        cmd = ["open", str(target)]
    elif sys.platform == "win32":
        cmd = ["explorer", str(target)]
    else:
        cmd = ["xdg-open", str(target)]

    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return {"opened": str(target.relative_to(HOME))}
