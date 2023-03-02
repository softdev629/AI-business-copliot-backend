import os
import logging
from fastapi import FastAPI, WebSocket, UploadFile, WebSocketDisconnect
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from dotenv import load_dotenv

load_dotenv()

UPLOAD_FOLDER = './pdfs'
ALLOWED_EXTENSIONS = {'pdf'}

app = FastAPI()

origins = [
    "http://localhost:3000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.post('/api/upload/{num}')
async def upload(file: UploadFile, num: str):
    path = Path(UPLOAD_FOLDER) / file.filename

    if file and allowed_file(file.filename):
        path.write_bytes(await file.read())
        reader = PdfReader(path)
        raw_text = ''
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                raw_text += text
        text_splitter = CharacterTextSplitter(separator="\n", chunk_size=1000, chunk_overlap=200, length_function=len)
        texts = text_splitter.split_text(raw_text)
        embeddings = OpenAIEmbeddings()
        docsearch = None
        if(os.path.exists(f"./store/{num}/index.faiss")):
            docsearch = FAISS.load_local(f"./store/{num}", embeddings);
            docsearch.add_texts(texts)
        else:
            docsearch = FAISS.from_texts(texts, embeddings)
        docsearch.save_local(f"./store/{num}")
        return {"state": "success"}
    return {"state": "error", "message": "Invalid file format"}

@app.websocket("/api/chat/{num}")
async def chat(websocket: WebSocket, num: str):
    await websocket.accept()
    chain = load_qa_chain(OpenAI(temperature=0), chain_type="stuff")
    embeddings = OpenAIEmbeddings()
    docsearch = FAISS.load_local(f"./store/{num}", embeddings)

    while True:
        try:
            logging.info("Hello!!!");
            query = await websocket.receive_text()
            docs = docsearch.similarity_search(query)
            completion = chain.run(input_documents=docs, question=query)
            await websocket.send_text(completion)
        except WebSocketDisconnect:
            break

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=True)