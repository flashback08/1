import uvicorn
from fastapi import FastAPI
from app.routes import router

app = FastAPI(title='QC Allocation Scheduler')
app.include_router(router, prefix='/api')

@app.get('/')
def health():
    return {'status':'ok'}

if __name__ == '__main__':
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000, reload=True)
