# ai_modules/s3_storage.py
"""
AWS S3 Storage Module for InsureRAG
Stores all LLM inputs/outputs, debate rounds, recommendations, and uploaded PDFs.

S3 Bucket Structure:
    insurerag-data-<account>/
    ├── queries/
    │   └── <timestamp>_<query_id>.json     ← full debate log + final recommendation
    ├── documents/
    │   └── <timestamp>_<doc_id>.json       ← extracted PDF text + metadata
    ├── user-uploads/
    │   └── <timestamp>_<filename>.pdf      ← raw user-uploaded PDFs
    └── summaries/
        └── <timestamp>_<filename>.json     ← user doc summaries from LLM
"""
import os
import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

# ─── Configuration ───────────────────────────────────────────────────────────
S3_BUCKET_NAME = os.getenv("S3_DATA_BUCKET", "insurerag-data-store")
S3_REGION = os.getenv("AWS_REGION", "ap-south-1")


def _get_s3_client():
    """Create a boto3 S3 client using env-based credentials."""
    try:
        return boto3.client(
            "s3",
            region_name=S3_REGION,
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        )
    except NoCredentialsError:
        logger.error("AWS credentials not found. S3 storage disabled.")
        return None


def _ensure_bucket_exists(s3):
    """Create the bucket if it doesn't exist."""
    try:
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
    except ClientError as e:
        error_code = int(e.response["Error"]["Code"])
        if error_code == 404:
            logger.info(f"Creating S3 bucket: {S3_BUCKET_NAME}")
            if S3_REGION == "us-east-1":
                s3.create_bucket(Bucket=S3_BUCKET_NAME)
            else:
                s3.create_bucket(
                    Bucket=S3_BUCKET_NAME,
                    CreateBucketConfiguration={"LocationConstraint": S3_REGION},
                )
        else:
            logger.error(f"S3 bucket error: {e}")
            raise


def _timestamp():
    return datetime.utcnow().strftime("%Y%m%d_%H%M%S")


# ─── Public API ──────────────────────────────────────────────────────────────

def upload_query_result(query_text: str, debate_rounds: list, final_consensus: str,
                        processing_time: float, chunks_used: int,
                        query_id: int = None) -> str:
    """
    Upload full query result (input query + debate rounds + final recommendation) to S3.
    Returns the S3 key of the uploaded object, or empty string on failure.
    """
    s3 = _get_s3_client()
    if not s3:
        return ""

    try:
        _ensure_bucket_exists(s3)

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "query_id": query_id,
            "input_query": query_text,
            "debate_rounds": debate_rounds,
            "final_recommendation": final_consensus,
            "processing_time_seconds": processing_time,
            "chunks_used": chunks_used,
        }

        key = f"queries/{_timestamp()}_{query_id or uuid.uuid4().hex[:8]}.json"
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=json.dumps(payload, indent=2, default=str),
            ContentType="application/json",
        )
        logger.info(f"Query result uploaded to S3: {key}")
        return key

    except Exception as e:
        logger.error(f"Failed to upload query result to S3: {e}")
        return ""


def upload_document_text(document_id: int, title: str, filename: str,
                         extracted_text: str) -> str:
    """
    Upload extracted PDF text + metadata to S3.
    Returns the S3 key.
    """
    s3 = _get_s3_client()
    if not s3:
        return ""

    try:
        _ensure_bucket_exists(s3)

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "document_id": document_id,
            "title": title,
            "original_filename": filename,
            "extracted_text": extracted_text,
            "text_length": len(extracted_text),
        }

        key = f"documents/{_timestamp()}_{document_id}.json"
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=json.dumps(payload, indent=2, default=str),
            ContentType="application/json",
        )
        logger.info(f"Document text uploaded to S3: {key}")
        return key

    except Exception as e:
        logger.error(f"Failed to upload document text to S3: {e}")
        return ""


def upload_raw_pdf(file_path: str, filename: str, prefix: str = "user-uploads") -> str:
    """
    Upload the raw PDF file to S3.
    Returns the S3 key.
    """
    s3 = _get_s3_client()
    if not s3:
        return ""

    try:
        _ensure_bucket_exists(s3)

        key = f"{prefix}/{_timestamp()}_{filename}"
        s3.upload_file(
            file_path,
            S3_BUCKET_NAME,
            key,
            ExtraArgs={"ContentType": "application/pdf"},
        )
        logger.info(f"PDF uploaded to S3: {key}")
        return key

    except Exception as e:
        logger.error(f"Failed to upload PDF to S3: {e}")
        return ""


def upload_user_doc_summary(filename: str, summary: str,
                            raw_text: str = "") -> str:
    """
    Upload user document summary (LLM output) to S3.
    Returns the S3 key.
    """
    s3 = _get_s3_client()
    if not s3:
        return ""

    try:
        _ensure_bucket_exists(s3)

        payload = {
            "timestamp": datetime.utcnow().isoformat(),
            "filename": filename,
            "llm_summary": summary,
            "input_text_preview": raw_text[:2000] if raw_text else "",
        }

        key = f"summaries/{_timestamp()}_{Path(filename).stem}.json"
        s3.put_object(
            Bucket=S3_BUCKET_NAME,
            Key=key,
            Body=json.dumps(payload, indent=2, default=str),
            ContentType="application/json",
        )
        logger.info(f"User doc summary uploaded to S3: {key}")
        return key

    except Exception as e:
        logger.error(f"Failed to upload user doc summary to S3: {e}")
        return ""


def list_s3_objects(prefix: str = "", max_keys: int = 50) -> list:
    """
    List objects in the S3 bucket under the given prefix.
    Returns list of dicts with key, size, last_modified.
    """
    s3 = _get_s3_client()
    if not s3:
        return []

    try:
        response = s3.list_objects_v2(
            Bucket=S3_BUCKET_NAME,
            Prefix=prefix,
            MaxKeys=max_keys,
        )

        objects = []
        for obj in response.get("Contents", []):
            objects.append({
                "key": obj["Key"],
                "size": obj["Size"],
                "last_modified": obj["LastModified"].isoformat(),
            })

        return objects

    except Exception as e:
        logger.error(f"Failed to list S3 objects: {e}")
        return []


def get_s3_object_content(key: str) -> dict:
    """
    Download and parse a JSON object from S3.
    Returns the parsed dict, or empty dict on failure.
    """
    s3 = _get_s3_client()
    if not s3:
        return {}

    try:
        response = s3.get_object(Bucket=S3_BUCKET_NAME, Key=key)
        body = response["Body"].read().decode("utf-8")
        return json.loads(body)

    except Exception as e:
        logger.error(f"Failed to get S3 object {key}: {e}")
        return {}
