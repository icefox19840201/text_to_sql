import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

def fastapi_init():
    app = FastAPI()
    STATIC_DIR = "static"
    os.makedirs(STATIC_DIR, exist_ok=True)
    # 添加 CORS 中间件
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # 挂载静态文件
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
    return app