import os
import logging
from fastapi import FastAPI, WebSocket, UploadFile, WebSocketDisconnect, Body
from pathlib import Path
from fastapi.middleware.cors import CORSMiddleware
from PyPDF2 import PdfReader

from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.vectorstores import FAISS
from langchain.chains.question_answering import load_qa_chain
from langchain.llms import OpenAI
from langchain.document_loaders import YoutubeLoader, TextLoader
from langchain import PromptTemplate
from langchain.memory import ConversationKGMemory
from dotenv import load_dotenv

load_dotenv()

UPLOAD_FOLDER = './files'
ALLOWED_EXTENSIONS = {'pdf', 'txt'}

app = FastAPI()

origins = [
    "https://seahorse-app-kbdql.ondigitalocean.app",
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
        fileext = file.filename.rsplit('.', 1)[1].lower()
        if(fileext == 'pdf'):
            reader = PdfReader(path)
            raw_text = ''
            for i, page in enumerate(reader.pages):
                text = page.extract_text()
                if text:
                    raw_text += text
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
            texts = text_splitter.split_text(raw_text)
            embeddings = OpenAIEmbeddings()
            if os.path.exists(f"./store/{num}/index.faiss"):
                docsearch = FAISS.load_local(f"./store/{num}", embeddings)
                docsearch.add_texts(texts)
            else:
                docsearch = FAISS.from_texts(texts, embeddings)
            docsearch.save_local(f"./store/{num}")
        else:
            loader = TextLoader(path)
            text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200, length_function=len)
            split_docs = loader.load_and_split(text_splitter)
            embeddings = OpenAIEmbeddings()
            if os.path.exists(f"./store/{num}/index.faiss"):
                docsearch = FAISS.load_local(f"./store/{num}", embeddings)
                docsearch.add_documents(split_docs, embeddings)
            else:
                docsearch = FAISS.from_documents(split_docs, embeddings)
            docsearch.save_local(f"./store/{num}")

        return {"state": "success"}
    return {"state": "error", "message": "Invalid file format"}

@app.post('/api/youtube/train/{num}')
async def train_youtube(num: int, url: str = Body(embed=True)):
    loader = YoutubeLoader.from_youtube_channel(url)
    data = loader.load()
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
    texts = text_splitter.split_documents(data)

    embeddings = OpenAIEmbeddings()
    if(os.path.exists(f"./store/{num}/index.faiss")):
        docsearch = FAISS.load_local(f"./store/{num}", embeddings)
        combineDoc = FAISS.load_local(f"./store/{num}", embeddings)
        docsearch.add_documents(texts)
    else:
        docsearch = FAISS.from_documents(texts, embeddings)
    docsearch.save_local(f"./store/{num}")
    return {"state": "success"}

template = """You are a chatbot having a conversation with a human.

Given the following extracted parts of a long document and a question, create a final answer.

{context}

{chat_history}
Human: {human_input}
Chatbot:"""

prompt = PromptTemplate(
    input_variables=["chat_history", "human_input", "context"],
    template=template
)

@app.websocket("/api/chat/{num}")
async def pdf_chat(websocket: WebSocket, num: str):
    await websocket.accept()
    llm = OpenAI(temperature=0)
    memory = ConversationKGMemory(llm=llm, memory_key="chat_history", input_key="human_input")
    chain = load_qa_chain(llm=llm, chain_type="stuff", memory=memory, verbose=True, prompt=prompt)
    embeddings = OpenAIEmbeddings()
    docsearch = FAISS.load_local(f"./store/{num}", embeddings)

    while True:
        try:
            query = await websocket.receive_text()
            docs = docsearch.similarity_search(query)
            completion = chain.run(input_documents=docs, human_input=query)
            await websocket.send_text(completion)
        except WebSocketDisconnect:
            break

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=9000, reload=True)
