from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


app = FastAPI(
    title="A Stock API",
    description="Python + Vue starter API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict[str, str]:
    return {"message": "Welcome to A Stock API"}


@app.get("/api/welcome")
async def welcome() -> dict[str, str]:
    return {
        "title": "欢迎来到 A Stock",
        "message": "Python 与 Vue 已经连接成功，可以开始构建你的应用了。",
        "status": "online",
    }


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
