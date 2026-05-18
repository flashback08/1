import uvicorn
from fastapi import FastAPI
from backend.app.routes import router
from backend.app.db import engine  # Imported your database engine and Base
from database.models import Base  # noqa: F401 — imports register all models with Base

app = FastAPI(title='QC Allocation Scheduler')

# Create all database tables in Neon if they don't exist yet
Base.metadata.create_all(bind=engine)

app.include_router(router, prefix='/api')

@app.get('/')
def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    uvicorn.run('backend.app.main:app', host='127.0.0.1', port=8000, reload=True)