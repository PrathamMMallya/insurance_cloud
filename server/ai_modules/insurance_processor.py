# ai_modules/insurance_processor.py
import os
import sys
import json
import time
import logging
from typing import List, Dict, Any, Tuple
import numpy as np
from pathlib import Path

# ── LangChain modern imports (0.3.x) ────────────────────────
import requests
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.embeddings.base import Embeddings
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.chat_models import ChatOpenAI
# Add the Django project to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Django setup
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
import django
django.setup()

from insurance.models import InsuranceDocument, DocumentChunk, InsuranceQuery

# Core imports
from dotenv import load_dotenv
import warnings
warnings.filterwarnings("ignore")

# Load .env from project root (2 levels up from ai_modules/)
_project_root = Path(__file__).resolve().parent.parent.parent
load_dotenv(_project_root / '.env')

import faiss
import fitz  # PyMuPDF
import re

from ai_modules.s3_storage import (
    upload_query_result,
    upload_document_text,
    upload_raw_pdf,
    upload_user_doc_summary,
)

logger = logging.getLogger(__name__)


class SimpleHFEmbeddings(Embeddings):
    """Lightweight HuggingFace API embeddings (no sentence-transformers required)."""

    def __init__(self, api_key: str, model: str = "BAAI/bge-small-en-v1.5"):
        self.api_url = f"https://api-inference.huggingface.co/models/{model}"
        self.headers = {"Authorization": f"Bearer {api_key}"}

    def _call_api(self, inputs):
        response = requests.post(
            self.api_url,
            headers=self.headers,
            json={
                "inputs": inputs,
                "options": {"wait_for_model": True}
            }
        )

        if response.status_code != 200:
            raise ValueError(f"HuggingFace API Error: {response.text}")

        return response.json()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        result = self._call_api(texts)

        # normalize output
        if isinstance(result, list) and isinstance(result[0], list):
            return result
        return [result]

    def embed_query(self, text: str) -> List[float]:
        result = self._call_api(text)

        # sometimes API returns nested list
        if isinstance(result[0], list):
            return result[0]

        return result

class InsuranceRAGProcessor:
    """RAG processor using Groq models only (no Ollama).

    Model A (GROQ_MODEL_A): Primary RAG model for insurance recommendations
    Model B (GROQ_MODEL_B): Keyword extraction and structured analysis
    """

    def __init__(self):
        self.hf_api_key = os.getenv("HUGGINGFACE_API_KEY")

        self.embeddings = SimpleHFEmbeddings(
    api_key=self.hf_api_key,
    model="BAAI/bge-small-en-v1.5"
)

        self.model_a = os.getenv("GROQ_MODEL_A", "llama-3.3-70b-versatile")
        self.model_b = os.getenv("GROQ_MODEL_B", "llama-3.1-8b-instant")
        self.groq_api_key = os.getenv("GROQ_API_KEY", "")
        self.llm = ChatOpenAI(
        openai_api_key=self.groq_api_key,
        base_url="https://api.groq.com/openai/v1",
        model_name=self.model_a,
        temperature=0
    )
        self.vector_stores: Dict = {}
        self.retrievers: Dict = {}
        self.rag_chain = None
        self.keyword_chain = None

    # =========================================================================
    # DOCUMENT LOADING & CHUNKING
    # =========================================================================

    def load_and_convert_document(self, file_path: str) -> str:
        """Load PDF and convert to markdown-like text using PyMuPDF"""
        try:
            logger.info(f"Converting document: {file_path}")
            doc = fitz.open(file_path)
            markdown_parts = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text("text")
                if text.strip():
                    markdown_parts.append(f"## Page {page_num + 1}\n\n{text.strip()}")

            doc.close()
            return "\n\n".join(markdown_parts)
        except Exception as e:
            logger.error(f"Error converting document: {e}")
            raise

    def preprocess_markdown_content(self, markdown_content: str) -> str:
        """Clean and preprocess markdown content for better chunking"""
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', markdown_content)
        content = re.sub(r'(\d+\.\s+[A-Za-z]+.*?)\n([A-Z])', r'\1\n\n\2', content)
        content = re.sub(
            r'(\d+\.\s+[A-Za-z][^0-9]*(?:Age|Diseases|Reimbursement|Premium|Highlights).*?)(?=\n\d+\.|\n##|\Z)',
            r'--- POLICY START ---\n\1\n--- POLICY END ---', content, flags=re.DOTALL
        )
        return content

    def get_optimized_chunk_strategies(
        self, markdown_content: str
    ) -> Tuple[List[Document], List[Document], List[Document]]:
        """Create optimized chunking strategies that preserve policy information"""
        processed_content = self.preprocess_markdown_content(markdown_content)

        # Strategy 1: Policy-based chunking
        policy_chunks: List[Document] = []
        policy_pattern = r'--- POLICY START ---\n(.*?)\n--- POLICY END ---'
        policies = re.findall(policy_pattern, processed_content, re.DOTALL)

        for i, policy in enumerate(policies):
            if len(policy.strip()) > 50:
                policy_chunks.append(Document(
                    page_content=policy.strip(),
                    metadata={'strategy': 'policy', 'policy_id': i}
                ))

        # Strategy 2: Semantic chunks
        semantic_splitter = RecursiveCharacterTextSplitter(
            chunk_size=800,
            chunk_overlap=200,
            length_function=len,
            separators=["\n--- POLICY END ---", "\n\n", "\n", ". ", " "]
        )
        semantic_chunks = semantic_splitter.create_documents([processed_content])
        for chunk in semantic_chunks:
            chunk.metadata['strategy'] = 'semantic'

        # Strategy 3: Header-based chunks
        headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
        markdown_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on, strip_headers=False
        )
        header_chunks = markdown_splitter.split_text(processed_content)
        for chunk in header_chunks:
            chunk.metadata['strategy'] = 'header'

        return policy_chunks, semantic_chunks, header_chunks

    # =========================================================================
    # DATABASE OPERATIONS
    # =========================================================================

    def save_chunks_to_database(
        self,
        document_id: int,
        policy_chunks: List[Document],
        semantic_chunks: List[Document],
        header_chunks: List[Document],
    ) -> None:
        """Save chunks to Django database with batched embedding calls"""
        try:
            document = InsuranceDocument.objects.get(id=document_id)
            DocumentChunk.objects.filter(document=document).delete()

            all_chunks = [
                ('policy', policy_chunks),
                ('semantic', semantic_chunks),
                ('header', header_chunks),
            ]

            chunk_counter = 0

            for strategy, chunks in all_chunks:
                if not chunks:
                    continue

                texts = [chunk.page_content for chunk in chunks]
                embeddings = self.embeddings.embed_documents(texts)  # single batch call

                for chunk, embedding in zip(chunks, embeddings):
                    DocumentChunk.objects.create(
                        document=document,
                        chunk_id=f"{strategy}_{chunk_counter}",
                        content=chunk.page_content,
                        strategy=strategy,
                        metadata=chunk.metadata,
                        embedding_vector=embedding,
                    )
                    chunk_counter += 1

            document.total_chunks = chunk_counter
            document.processed = True
            document.save()

            logger.info(f"Saved {chunk_counter} chunks for document {document_id}")

        except Exception as e:
            logger.error(f"Error saving chunks to database: {e}")
            raise

    def load_chunks_from_database(self, document_id: int = None) -> List[Document]:
        """Load chunks from Django database"""
        try:
            qs = (
                DocumentChunk.objects.filter(document_id=document_id)
                if document_id
                else DocumentChunk.objects.all()
            )

            documents = []
            for chunk in qs:
                doc = Document(
                    page_content=chunk.content,
                    metadata={
                        'strategy': chunk.strategy,
                        'chunk_id': chunk.chunk_id,
                        'document_id': chunk.document.id,
                        **chunk.metadata,
                    },
                )
                documents.append(doc)

            logger.info(f"Loaded {len(documents)} chunks from database")
            return documents

        except Exception as e:
            logger.error(f"Error loading chunks from database: {e}")
            raise

    # =========================================================================
    # VECTOR STORE SETUP
    # =========================================================================

    def setup_vector_stores_from_db(self, document_id: int = None) -> Dict:
        """Create FAISS vector stores from database chunks"""
        try:
            all_chunks = self.load_chunks_from_database(document_id)

            if not all_chunks:
                logger.warning("No chunks found in database")
                return {}

            embeddings_list: List[List[float]] = []
            for chunk in all_chunks:
                db_chunk = DocumentChunk.objects.get(
                    document_id=chunk.metadata.get('document_id'),
                    chunk_id=chunk.metadata.get('chunk_id'),
                )
                if db_chunk.embedding_vector:
                    embeddings_list.append(db_chunk.embedding_vector)
                else:
                    embedding = self.embeddings.embed_query(chunk.page_content)
                    embeddings_list.append(embedding)
                    db_chunk.embedding_vector = embedding
                    db_chunk.save()

            # Build main FAISS index
            embeddings_array = np.array(embeddings_list, dtype=np.float32)
            dim = embeddings_array.shape[1]

            index = faiss.IndexFlatL2(dim)
            index.add(embeddings_array)

            vector_store = FAISS(
                embedding_function=self.embeddings,
                index=index,
                docstore=InMemoryDocstore({i: doc for i, doc in enumerate(all_chunks)}),
                index_to_docstore_id={i: i for i in range(len(all_chunks))},
            )

            stores: Dict = {'main': vector_store}

            # Policy-only store
            policy_indices = [
                i for i, doc in enumerate(all_chunks)
                if doc.metadata.get('strategy') == 'policy'
            ]
            if policy_indices:
                policy_chunks = [all_chunks[i] for i in policy_indices]
                policy_array = np.array(
                    [embeddings_list[i] for i in policy_indices], dtype=np.float32
                )
                policy_index = faiss.IndexFlatL2(dim)
                policy_index.add(policy_array)

                stores['policy'] = FAISS(
                    embedding_function=self.embeddings,
                    index=policy_index,
                    docstore=InMemoryDocstore(
                        {i: doc for i, doc in enumerate(policy_chunks)}
                    ),
                    index_to_docstore_id={i: i for i in range(len(policy_chunks))},
                )

            self.vector_stores = stores
            logger.info(f"Vector stores created with {len(all_chunks)} total chunks")
            return stores

        except Exception as e:
            logger.error(f"Error setting up vector stores: {e}")
            raise

    def create_smart_retrievers(self) -> Dict:
        """Create retrievers with different search strategies"""
        if not self.vector_stores:
            raise ValueError("Vector stores not initialized. Call setup_vector_stores_from_db first.")

        retrievers: Dict = {}

        retrievers['primary'] = self.vector_stores['main'].as_retriever(
            search_type="similarity",
            search_kwargs={'k': 6},
        )
        retrievers['diverse'] = self.vector_stores['main'].as_retriever(
            search_type="mmr",
            search_kwargs={'k': 4, 'fetch_k': 10, 'lambda_mult': 0.3},
        )
        if 'policy' in self.vector_stores:
            retrievers['policy'] = self.vector_stores['policy'].as_retriever(
                search_type="similarity",
                search_kwargs={'k': 5},
            )

        self.retrievers = retrievers
        return retrievers

    # =========================================================================
    # RETRIEVAL
    # =========================================================================

    def intelligent_hybrid_retrieve(self, question: str, top_k: int = 5) -> List[Document]:
        """Hybrid retrieval with deduplication and keyword-based re-ranking"""
        if not self.retrievers:
            raise ValueError("Retrievers not initialized. Call create_smart_retrievers first.")

        question_lower = question.lower()
        key_terms: set = set()

        # Manual keyword extraction
        age_match = re.search(r'age[:\s]*(\d+)', question_lower)
        if age_match:
            key_terms.add(f"age {age_match.group(1)}")

        conditions = [
            'diabetes', 'heart', 'cancer', 'hypertension', 'kidney',
            'liver', 'asthma', 'thyroid', 'bp', 'cholesterol',
        ]
        for condition in conditions:
            if condition in question_lower:
                key_terms.add(condition)

        budget_match = re.search(r'₹(\d+,?\d*)', question)
        if budget_match:
            key_terms.add(f"budget {budget_match.group(1)}")

        # LLM keyword extraction (Model B)
        extractor = self.create_keyword_extractor_chain()
        try:
            structured_keywords = extractor.invoke({"question": question_lower})
            logger.info(f"Extracted keywords: {structured_keywords}")

            for item in structured_keywords.split('\n'):
                item_lower = item.lower().strip()
                if not item_lower:
                    continue
                if "age" in item_lower:
                    m = re.search(r'age[:\s]*(\d+)', item_lower)
                    if m:
                        key_terms.add(f"age {m.group(1)}")
                elif "health condition" in item_lower or "condition" in item_lower:
                    for cond in item_lower.split(":")[-1].split(","):
                        cond = cond.strip().strip('-').strip()
                        if cond and len(cond) > 2:
                            key_terms.add(cond)
                elif "budget" in item_lower:
                    m = re.search(r'₹(\d+,?\d*)', item_lower)
                    if m:
                        key_terms.add(f"budget {m.group(1)}")
                elif "coverage" in item_lower:
                    for cov in item_lower.split(":")[-1].split(","):
                        cov = cov.strip().strip('-').strip()
                        if cov and len(cov) > 2:
                            key_terms.add(cov)
        except Exception as e:
            logger.warning(f"Keyword extraction failed, using manual terms: {e}")

        key_terms_list = list(key_terms)
        logger.info(f"Final key terms: {key_terms_list}")

        all_docs: List[Document] = []
        seen_content: set = set()

        for name, retriever in self.retrievers.items():
            try:
                docs = retriever.invoke(question)
                for doc in docs:
                    content_signature = ' '.join(doc.page_content.split()[:20])
                    content_hash = hash(content_signature)
                    if content_hash in seen_content:
                        continue
                    seen_content.add(content_hash)

                    relevance_score = sum(
                        1 for term in key_terms_list
                        if term in doc.page_content.lower()
                    )
                    doc.metadata['retriever'] = name
                    doc.metadata['relevance_score'] = relevance_score
                    all_docs.append(doc)
            except Exception as e:
                logger.error(f"Error with {name} retriever: {e}")

        all_docs.sort(key=lambda x: x.metadata.get('relevance_score', 0), reverse=True)
        return all_docs[:top_k]

    # =========================================================================
    # CHAINS
    # =========================================================================

    def create_rag_chain(self):
        """Create RAG chain using Groq Model A"""
        if not self.retrievers:
            raise ValueError("Retrievers not initialized.")

        prompt_template = ChatPromptTemplate.from_template("""
You are an expert health insurance advisor in India. Analyze the provided insurance policies
and recommend the most suitable options based on the user's specific needs.

USER REQUIREMENTS:
{question}

AVAILABLE INSURANCE POLICIES:
{context}

INSTRUCTIONS:
1. Carefully analyze each policy option provided
2. Match the user's age, health condition, and budget with suitable policies
3. Consider premium affordability (monthly income vs annual premium)
4. Ensure the health condition is covered under the policy
5. Provide 2-3 specific policy recommendations with clear reasoning
6. If no suitable policy exists, explain why and suggest alternatives

RESPONSE FORMAT:
## Recommended Insurance Policies

### Policy 1: [Policy Name]
- **Why suitable**: [Specific reasons]
- **Coverage**: [What's covered for user's condition]
- **Premium**: [Annual premium and monthly breakdown]
- **Key Benefits**: [Relevant benefits]

### Policy 2: [Policy Name]
- **Why suitable**: [Specific reasons]
- **Coverage**: [What's covered for user's condition]
- **Premium**: [Annual premium and monthly breakdown]
- **Key Benefits**: [Relevant benefits]

## Summary
[Brief summary of why these policies are recommended]

Base your recommendations ONLY on the provided policy information.
""")

        model = ChatOpenAI(
            openai_api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            model_name=self.model_b,
            temperature=0.1,
            max_tokens=300,
        )
        logger.info(f"Using Groq Model A: {self.model_a}")

        def retrieval_chain(question: str) -> Dict:
            docs = self.intelligent_hybrid_retrieve(question, top_k=5)
            context = self.format_context(docs)
            return {"context": context, "question": question}

        self.rag_chain = retrieval_chain | prompt_template | model | StrOutputParser()
        return self.rag_chain

    def create_keyword_extractor_chain(self):
        """Model B-powered chain to extract structured keywords"""
        model = model = self.llm

        prompt_template = ChatPromptTemplate.from_template("""
You are a helpful assistant. Extract the following from the user's message:
1. Age
2. Health conditions (like asthma, thyroid, diabetes, etc.)
3. Budget or financial constraints (the exact value like 15000rs, etc. if given)
4. Desired coverage (doctor visits, prescriptions, hospitalization, etc.)

Input:
{question}

Return each extracted field on its own line in the format:
Age: <value>
Health Conditions: <value1>, <value2>
Budget: <value>
Coverage: <value1>, <value2>

If a field is not mentioned, write "Not specified".
""")

        self.keyword_chain = prompt_template | model | StrOutputParser()
        return self.keyword_chain

    def format_context(self, docs: List[Document]) -> str:
        """Format documents for context"""
        if not docs:
            return "No relevant insurance policies found."

        formatted_parts = []
        for i, doc in enumerate(docs, 1):
            retriever_info = doc.metadata.get('retriever', 'unknown')
            strategy_info = doc.metadata.get('strategy', 'unknown')
            relevance_score = doc.metadata.get('relevance_score', 0)

            content = doc.page_content.strip()
            content = re.sub(r'--- POLICY (START|END) ---', '', content).strip()

            formatted_parts.append(
                f"=== POLICY OPTION {i} "
                f"(via {retriever_info}-{strategy_info}, relevance: {relevance_score}) ===\n"
                f"{content}\n"
            )

        return "\n".join(formatted_parts)

    # =========================================================================
    # DOCUMENT PROCESSING
    # =========================================================================

    def process_document(self, file_path: str, document_id: int) -> bool:
        """Process a document and save chunks to database"""
        try:
            markdown_content = self.load_and_convert_document(file_path)
            policy_chunks, semantic_chunks, header_chunks = self.get_optimized_chunk_strategies(
                markdown_content
            )
            self.save_chunks_to_database(document_id, policy_chunks, semantic_chunks, header_chunks)

            # ── Upload extracted text + raw PDF to S3 ──
            try:
                doc = InsuranceDocument.objects.get(id=document_id)
                upload_document_text(
                    document_id=document_id,
                    title=doc.title,
                    filename=doc.original_filename,
                    extracted_text=markdown_content,
                )
                upload_raw_pdf(file_path, doc.original_filename, prefix="knowledge-base")
            except Exception as s3_err:
                logger.warning(f"S3 upload failed (non-fatal): {s3_err}")

            logger.info(f"Successfully processed document {document_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing document: {e}")
            return False

    def initialize_system(self, document_id: int = None) -> bool:
        """Initialize the RAG system from database"""
        try:
            self.setup_vector_stores_from_db(document_id)
            self.create_smart_retrievers()
            self.create_rag_chain()
            logger.info("RAG system initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Error initializing system: {e}")
            return False

    # =========================================================================
    # USER DOCUMENT SUMMARIZATION
    # =========================================================================

    def summarize_user_document(self, file_path: str) -> str:
        """Extract and summarize a user-uploaded PDF for insurance context"""
        try:
            raw_text = self.load_and_convert_document(file_path)

            if not raw_text.strip():
                return "Could not extract text from the uploaded document."

            max_chars = 6000
            if len(raw_text) > max_chars:
                raw_text = raw_text[:max_chars] + "\n...[document truncated]"

            model = ChatOpenAI(
    openai_api_key=self.groq_api_key,
    base_url="https://api.groq.com/openai/v1",
    model_name=self.model_b,
    temperature=0.1,
    max_tokens=300,
)

            summary_prompt = ChatPromptTemplate.from_template("""
You are an insurance analysis assistant. A user has uploaded a personal document
(could be a medical report, vehicle registration, health checkup, property document, etc.).

Extract and summarize the KEY INFORMATION relevant for insurance recommendation:

DOCUMENT TEXT:
{document_text}

Provide a concise summary in this format:
- **Document Type**: (medical report / vehicle RC / health checkup / property doc / etc.)
- **Key Details**: (name, age, vehicle type, property details, etc.)
- **Health Conditions / Risk Factors**: (if medical doc)
- **Coverage Needs**: (what kind of insurance this person likely needs)
- **Important Numbers**: (any policy numbers, vehicle numbers, medical values, etc.)

Keep it concise — this summary will be used as context for insurance queries.
""")

            chain = summary_prompt | model | StrOutputParser()
            summary = chain.invoke({"document_text": raw_text})
            logger.info("User document summarized successfully")

            # ── Upload summary to S3 ──
            try:
                upload_user_doc_summary(
                    filename=os.path.basename(file_path),
                    summary=summary,
                    raw_text=raw_text,
                )
            except Exception as s3_err:
                logger.warning(f"S3 upload of user doc summary failed (non-fatal): {s3_err}")

            return summary

        except Exception as e:
            logger.error(f"Error summarizing user document: {e}")
            return f"Error summarizing document: {str(e)}"

    # =========================================================================
    # MULTI-ROUND DEBATE
    # =========================================================================

    def _run_debate(self, question: str, context: str, num_rounds: int = 3) -> Dict[str, Any]:
        """Run a multi-round debate between Model A and Model B"""
        model_a = ChatOpenAI(
            openai_api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            model_name=self.model_b,
            temperature=0.1,
            max_tokens=300,
        )
        model_b = ChatOpenAI(
            openai_api_key=self.groq_api_key,
            base_url="https://api.groq.com/openai/v1",
            model_name=self.model_b,
            temperature=0.2,
            max_tokens=1500,
        )

        debate_log: List[Dict] = []

        # Round 1: Model A proposes
        chain_a1 = ChatPromptTemplate.from_template("""
You are Model A — an expert health insurance advisor in India.
Analyze the insurance policies below and recommend the best options for the user.

USER REQUIREMENTS:
{question}

AVAILABLE INSURANCE POLICIES:
{context}

Provide 2-3 specific policy recommendations with reasoning, coverage details,
premiums, and key benefits. Base your recommendations ONLY on the provided policy information.
""") | model_a | StrOutputParser()

        model_a_proposal = chain_a1.invoke({"question": question, "context": context})
        debate_log.append({
            "round": 1,
            "model": f"Model A ({self.model_a})",
            "role": "Proposer",
            "content": model_a_proposal,
        })
        logger.info("Debate Round 1 complete")
        time.sleep(1)

        # Round 2: Model B critiques
        chain_b = ChatPromptTemplate.from_template("""
You are Model B — an insurance validation expert.

USER REQUIREMENTS:
{question}

AVAILABLE POLICIES:
{context}

MODEL A's RECOMMENDATIONS:
{proposal}

Your task:
1. Identify ERRORS or MISMATCHES (wrong age range, uncovered conditions, etc.)
2. Check if the premium fits the user's budget
3. Identify any BETTER policy options that Model A missed
4. Rate Model A's recommendation quality (1-10)
5. Suggest specific improvements

Be honest and thorough. If Model A got it right, acknowledge that.
""") | model_b | StrOutputParser()

        model_b_critique = chain_b.invoke({
            "question": question,
            "context": context,
            "proposal": model_a_proposal,
        })
        debate_log.append({
            "round": 2,
            "model": f"Model B ({self.model_b})",
            "role": "Critic",
            "content": model_b_critique,
        })
        logger.info("Debate Round 2 complete")
        time.sleep(1)

        # Round 3: Model A refines
        chain_a2 = ChatPromptTemplate.from_template("""
You are Model A — an expert health insurance advisor.
Model B has critiqued your initial recommendations. Provide REFINED final recommendations.

USER REQUIREMENTS:
{question}

AVAILABLE POLICIES:
{context}

YOUR ORIGINAL RECOMMENDATIONS:
{proposal}

MODEL B's CRITIQUE:
{critique}

Based on Model B's feedback:
1. Address each valid criticism
2. Correct any errors identified
3. Include any better policies Model B suggested
4. Provide your REFINED final recommendations

Format:
## Final Recommended Insurance Policies

### Policy 1: [Name]
- **Why suitable**: ...
- **Coverage**: ...
- **Premium**: ...
- **Key Benefits**: ...

### Policy 2: [Name]
- **Why suitable**: ...
- **Coverage**: ...
- **Premium**: ...
- **Key Benefits**: ...

## Summary
[Final summary incorporating all valid feedback]
""") | model_a | StrOutputParser()

        model_a_refined = chain_a2.invoke({
            "question": question,
            "context": context,
            "proposal": model_a_proposal,
            "critique": model_b_critique,
        })
        debate_log.append({
            "round": 3,
            "model": f"Model A ({self.model_a})",
            "role": "Refined Proposal",
            "content": model_a_refined,
        })
        logger.info("Debate Round 3 complete")

        return {
            "debate_rounds": debate_log,
            "final_consensus": model_a_refined,
            "total_rounds": 3,
        }

    def query_insurance(self, question: str, save_to_db: bool = True) -> Dict[str, Any]:
        """Query using multi-round debate. Returns final_consensus + debate_rounds."""
        if not self.rag_chain:
            raise ValueError("RAG system not initialized. Call initialize_system first.")

        try:
            start_time = time.time()

            retrieved_docs = self.intelligent_hybrid_retrieve(question, top_k=5)
            chunk_ids = [doc.metadata.get('chunk_id', '') for doc in retrieved_docs]
            context = self.format_context(retrieved_docs)

            debate_result = self._run_debate(question, context, num_rounds=3)

            processing_time = time.time() - start_time

            query_id = None
            if save_to_db:
                q = InsuranceQuery.objects.create(
                    query_text=question,
                    response_text=debate_result['final_consensus'],
                    retrieved_chunks=chunk_ids,
                    processing_time=processing_time,
                )
                query_id = q.id

            # ── Upload full debate result to S3 ──
            try:
                s3_key = upload_query_result(
                    query_text=question,
                    debate_rounds=debate_result['debate_rounds'],
                    final_consensus=debate_result['final_consensus'],
                    processing_time=round(processing_time, 2),
                    chunks_used=len(chunk_ids),
                    query_id=query_id,
                )
            except Exception as s3_err:
                logger.warning(f"S3 upload failed (non-fatal): {s3_err}")
                s3_key = ""

            logger.info(f"Debate query processed in {processing_time:.2f}s")

            return {
                'final_consensus': debate_result['final_consensus'],
                'debate_rounds': debate_result['debate_rounds'],
                'total_rounds': debate_result['total_rounds'],
                'processing_time': round(processing_time, 2),
                'chunks_used': len(chunk_ids),
                's3_key': s3_key,
            }

        except Exception as e:
            logger.error(f"Error processing debate query: {e}")
            raise

    # =========================================================================
    # UTILITIES
    # =========================================================================

    @staticmethod
    def clear_all_data() -> bool:
        """Clear all data from database"""
        try:
            DocumentChunk.objects.all().delete()
            InsuranceDocument.objects.all().delete()
            InsuranceQuery.objects.all().delete()
            logger.info("All data cleared from database")
            return True
        except Exception as e:
            logger.error(f"Error clearing data: {e}")
            return False