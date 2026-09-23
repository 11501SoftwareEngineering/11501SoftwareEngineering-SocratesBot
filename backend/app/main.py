from fastapi import FastAPI

app = FastAPI(title="SocratesBot")


@app.get("/")
def read_root():
    return {"status": "ok"}
