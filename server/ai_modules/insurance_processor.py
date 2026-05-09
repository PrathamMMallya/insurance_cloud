# ai_modules/insurance_processor.py

import os
import sys
import time
import logging
import requests
import numpy as np
import faiss
import fitz
import re

from pathlib import Path
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass, field
from dotenv import load_dotenv

# -----------------------------------------------------------------------------
# DJANGO SETUP
# -----------------------------------------------------------------------------

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

import django
django.setup()

from insurance.models import InsuranceDocument, DocumentChunk, InsuranceQuery

from ai_modules.s3_storage import (
    upload_query_result,
    upload_document_text,
    upload_raw_pdf,
    upload_user_doc_summary,
)

# -----------------------------------------------------------------------------
# ENV
# -----------------------------------------------------------------------------

_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / ".env")

logger = logging.getLogger(__name__)

# -----------------------------------------------------------------------------
# LIGHTWEIGHT DOCUMENT CLASS
# -----------------------------------------------------------------------------

@dataclass
class SimpleDocument:
    page_content: str
    metadata: Dict[str, Any] = field(default_factory=dict)

# -----------------------------------------------------------------------------
# LIGHTWEIGHT TEXT SPLITTERS
# -----------------------------------------------------------------------------

class SimpleTextSplitter:

    def __init__(self, chunk_size=800, chunk_overlap=200):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str) -> List[str]:

        chunks = []
        start = 0

        while start < len(text):
            end = start + self.chunk_size
            chunk = text[start:end]
            chunks.append(chunk)

            start += (self.chunk_size - self.chunk_overlap)

        return chunks

# -----------------------------------------------------------------------------
# LIGHTWEIGHT GROQ CLIENT
# -----------------------------------------------------------------------------

class GroqLLM:

    def __init__(self, api_key, model, temperature=0.1, max_tokens=1000):
        self.api_key = api_key
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens

    def invoke(self, prompt: str) -> str:

        response = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "temperature": self.temperature,
                "max_tokens": self.max_tokens,
            },
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(f"Groq API Error: {response.text}")

        return response.json()["choices"][0]["message"]["content"]

# -----------------------------------------------------------------------------
# LIGHTWEIGHT EMBEDDINGS
# -----------------------------------------------------------------------------

class SimpleHFEmbeddings:

    def __init__(self, api_key, model="BAAI/bge-small-en-v1.5"):

        self.api_url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}"

        self.headers = {
            "Authorization": f"Bearer {api_key}"
        }

    def _call_api(self, inputs):

        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={
                "inputs": inputs,
                "options": {
                    "wait_for_model": True
                }
            },
            timeout=120
        )

        if response.status_code != 200:
            raise Exception(response.text)

        return response.json()

    def embed_documents(self, texts: List[str]):

        result = self._call_api(texts)

        if isinstance(result[0], list):
            return result

        return [result]

    def embed_query(self, text: str):

        result = self._call_api(text)

        if isinstance(result[0], list):
            return result[0]

        return result

# -----------------------------------------------------------------------------
# SIMPLE VECTOR STORE
# -----------------------------------------------------------------------------

class SimpleVectorStore:

    def __init__(self, documents, embeddings):

        self.documents = documents
        self.embeddings = np.array(embeddings).astype("float32")

        dim = self.embeddings.shape[1]

        self.index = faiss.IndexFlatL2(dim)
        self.index.add(self.embeddings)

    def search(self, query_embedding, top_k=5):

        query = np.array([query_embedding]).astype("float32")

        distances, indices = self.index.search(query, top_k)

        results = []

        for idx in indices[0]:
            if idx < len(self.documents):
                results.append(self.documents[idx])

        return results

# -----------------------------------------------------------------------------
# MAIN PROCESSOR
# -----------------------------------------------------------------------------

class InsuranceRAGProcessor:

    def __init__(self):

        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.groq_api_key = os.getenv("GROQ_API_KEY")

        self.model_a = os.getenv(
            "GROQ_MODEL_A",
            "llama-3.3-70b-versatile"
        )

        self.model_b = os.getenv(
            "GROQ_MODEL_B",
            "llama-3.1-8b-instant"
        )

        self.embeddings = SimpleHFEmbeddings(
            api_key=self.hf_api_key
        )

        self.vector_store = None
        self.documents = []

    # =========================================================================
    # DOCUMENT LOADING
    # =========================================================================

    def load_and_convert_document(self, file_path):

        logger.info(f"Loading PDF: {file_path}")

        doc = fitz.open(file_path)

        text_parts = []

        for page_num in range(len(doc)):

            page = doc[page_num]

            text = page.get_text("text")

            if text.strip():
                text_parts.append(
                    f"## Page {page_num + 1}\n\n{text}"
                )

        doc.close()

        return "\n\n".join(text_parts)

    # =========================================================================
    # PREPROCESS
    # =========================================================================

    def preprocess_markdown_content(self, content):

        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)

        return content

    # =========================================================================
    # CHUNKING
    # =========================================================================

    def get_optimized_chunk_strategies(self, markdown_content):

        processed = self.preprocess_markdown_content(markdown_content)

        splitter = SimpleTextSplitter(
            chunk_size=800,
            chunk_overlap=200
        )

        chunks = splitter.split_text(processed)

        docs = []

        for i, chunk in enumerate(chunks):

            docs.append(
                SimpleDocument(
                    page_content=chunk,
                    metadata={
                        "chunk_id": f"chunk_{i}",
                        "strategy": "semantic"
                    }
                )
            )

        return docs

    # =========================================================================
    # SAVE CHUNKS
    # =========================================================================

    def save_chunks_to_database(self, document_id, chunks):

        document = InsuranceDocument.objects.get(id=document_id)

        DocumentChunk.objects.filter(
            document=document
        ).delete()

        texts = [c.page_content for c in chunks]

        embeddings = self.embeddings.embed_documents(texts)

        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):

            DocumentChunk.objects.create(
                document=document,
                chunk_id=f"chunk_{i}",
                content=chunk.page_content,
                strategy="semantic",
                metadata=chunk.metadata,
                embedding_vector=embedding,
            )

        document.total_chunks = len(chunks)
        document.processed = True
        document.save()

        logger.info(f"Saved {len(chunks)} chunks")

    # =========================================================================
    # LOAD CHUNKS
    # =========================================================================

    def load_chunks_from_database(self):

        docs = []

        chunks = DocumentChunk.objects.all()

        for chunk in chunks:

            docs.append(
                SimpleDocument(
                    page_content=chunk.content,
                    metadata={
                        "chunk_id": chunk.chunk_id,
                        "strategy": chunk.strategy,
                    }
                )
            )

        return docs

    # =========================================================================
    # VECTOR STORE
    # =========================================================================

    def setup_vector_store(self):

        docs = self.load_chunks_from_database()

        if not docs:
            logger.warning("No chunks found")
            return

        embeddings = []

        for chunk in DocumentChunk.objects.all():

            if chunk.embedding_vector:
                embeddings.append(chunk.embedding_vector)

        self.vector_store = SimpleVectorStore(
            docs,
            embeddings
        )

        self.documents = docs

        logger.info("FAISS vector store initialized")

    # =========================================================================
    # RETRIEVAL
    # =========================================================================

    def intelligent_hybrid_retrieve(self, question, top_k=5):

        query_embedding = self.embeddings.embed_query(question)

        docs = self.vector_store.search(
            query_embedding,
            top_k=top_k
        )

        return docs

    # =========================================================================
    # FORMAT CONTEXT
    # =========================================================================

    def format_context(self, docs):

        formatted = []

        for i, doc in enumerate(docs, 1):

            formatted.append(
                f"=== POLICY OPTION {i} ===\n"
                f"{doc.page_content}\n"
            )

        return "\n".join(formatted)

    # =========================================================================
    # LLM CALL
    # =========================================================================

    def ask_llm(self, prompt, model=None, temperature=0.1, max_tokens=1000):

        llm = GroqLLM(
            api_key=self.groq_api_key,
            model=model or self.model_a,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        return llm.invoke(prompt)

    # =========================================================================
    # PROCESS DOCUMENT
    # =========================================================================

    def process_document(self, file_path, document_id):

        try:

            markdown = self.load_and_convert_document(file_path)

            chunks = self.get_optimized_chunk_strategies(markdown)

            self.save_chunks_to_database(
                document_id,
                chunks
            )

            try:

                doc = InsuranceDocument.objects.get(
                    id=document_id
                )

                upload_document_text(
                    document_id=document_id,
                    title=doc.title,
                    filename=doc.original_filename,
                    extracted_text=markdown,
                )

                upload_raw_pdf(
                    file_path,
                    doc.original_filename,
                    prefix="knowledge-base"
                )

            except Exception as e:
                logger.warning(f"S3 upload failed: {e}")

            return True

        except Exception as e:

            logger.error(str(e))

            return False

    # =========================================================================
    # INIT SYSTEM
    # =========================================================================

    def initialize_system(self):

        self.setup_vector_store()

        return True

    # =========================================================================
    # USER DOCUMENT SUMMARY
    # =========================================================================

    def summarize_user_document(self, file_path):

        raw_text = self.load_and_convert_document(file_path)

        raw_text = raw_text[:6000]

        prompt = f"""
You are an insurance assistant.

Summarize the document.

DOCUMENT:
{raw_text}

Return:
- Document Type
- Key Details
- Health Conditions
- Coverage Needs
- Important Numbers
"""

        summary = self.ask_llm(
            prompt,
            model=self.model_b,
            max_tokens=400
        )

        try:

            upload_user_doc_summary(
                filename=os.path.basename(file_path),
                summary=summary,
                raw_text=raw_text,
            )

        except Exception as e:
            logger.warning(f"S3 summary upload failed: {e}")

        return summary

    # =========================================================================
    # MULTI AGENT DEBATE
    # =========================================================================

    def _run_debate(self, question, context):

        debate_log = []

        # ROUND 1

        prompt1 = f"""
You are an insurance advisor.

QUESTION:
{question}

POLICIES:
{context}

Recommend best policies.
"""

        response1 = self.ask_llm(
            prompt1,
            model=self.model_a,
            max_tokens=800
        )

        debate_log.append({
            "round": 1,
            "model": self.model_a,
            "role": "Proposer",
            "content": response1,
        })

        time.sleep(1)

        # ROUND 2

        prompt2 = f"""
You are an insurance validator.

QUESTION:
{question}

POLICIES:
{context}

MODEL A RESPONSE:
{response1}

Critique mistakes and suggest improvements.
"""

        response2 = self.ask_llm(
            prompt2,
            model=self.model_b,
            max_tokens=800
        )

        debate_log.append({
            "round": 2,
            "model": self.model_b,
            "role": "Critic",
            "content": response2,
        })

        time.sleep(1)

        # ROUND 3

        prompt3 = f"""
You are Model A.

QUESTION:
{question}

POLICIES:
{context}

ORIGINAL:
{response1}

CRITIQUE:
{response2}

Generate final improved recommendation.
"""

        final_response = self.ask_llm(
            prompt3,
            model=self.model_a,
            max_tokens=1200
        )

        debate_log.append({
            "round": 3,
            "model": self.model_a,
            "role": "Final",
            "content": final_response,
        })

        return {
            "debate_rounds": debate_log,
            "final_consensus": final_response,
            "total_rounds": 3,
        }

    # =========================================================================
    # QUERY
    # =========================================================================

    def query_insurance(self, question, save_to_db=True):

        start = time.time()

        docs = self.intelligent_hybrid_retrieve(
            question,
            top_k=5
        )

        context = self.format_context(docs)

        debate_result = self._run_debate(
            question,
            context
        )

        processing_time = time.time() - start

        chunk_ids = [
            d.metadata.get("chunk_id", "")
            for d in docs
        ]

        query_id = None

        if save_to_db:

            q = InsuranceQuery.objects.create(
                query_text=question,
                response_text=debate_result["final_consensus"],
                retrieved_chunks=chunk_ids,
                processing_time=processing_time,
            )

            query_id = q.id

        try:

            s3_key = upload_query_result(
                query_text=question,
                debate_rounds=debate_result["debate_rounds"],
                final_consensus=debate_result["final_consensus"],
                processing_time=round(processing_time, 2),
                chunks_used=len(chunk_ids),
                query_id=query_id,
            )

        except Exception as e:

            logger.warning(f"S3 upload failed: {e}")

            s3_key = ""

        return {
            "final_consensus": debate_result["final_consensus"],
            "debate_rounds": debate_result["debate_rounds"],
            "total_rounds": 3,
            "processing_time": round(processing_time, 2),
            "chunks_used": len(chunk_ids),
            "s3_key": s3_key,
        }

    # =========================================================================
    # CLEAR
    # =========================================================================

    @staticmethod
    def clear_all_data():

        try:

            DocumentChunk.objects.all().delete()
            InsuranceDocument.objects.all().delete()
            InsuranceQuery.objects.all().delete()

            logger.info("All DB data cleared")

            return True

        except Exception as e:

            logger.error(str(e))

            return False