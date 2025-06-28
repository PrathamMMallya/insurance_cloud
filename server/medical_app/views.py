from django.shortcuts import render, redirect
from django.http import FileResponse, Http404
from django.contrib import messages
from .models import MedicalRecord
from ai_modules.summarizer.processor import summarize_and_convert

import fitz  # PyMuPDF
import docx
import os


def extract_text_from_file(uploaded_file):
    if uploaded_file.name.endswith('.pdf'):
        with fitz.open(stream=uploaded_file.read(), filetype="pdf") as doc:
            return "\n".join([page.get_text() for page in doc])
    elif uploaded_file.name.endswith('.docx'):
        doc = docx.Document(uploaded_file)
        return "\n".join([p.text for p in doc.paragraphs])
    return ""


def remove_prompt_lines(summary: str) -> str:
    lines = summary.splitlines()
    cleaned = [
        line for line in lines
        if not line.strip().lower().startswith((
            "if it's", "include age", "key details for", "summary should help", "medical history:"
        ))
    ]
    return "\n".join(cleaned).strip()


def index(request):
    if request.method == 'POST':
        patient_name = request.POST.get('patient_name', '').strip()
        uploaded_file = request.FILES.get('report_file')
        report_text = request.POST.get('report_text', '').strip()

        if uploaded_file:
            report_text = extract_text_from_file(uploaded_file)

        report_text = report_text.replace("<n>", "\n").strip()

        if not report_text:
            return render(request, 'index.html', {
                'records': MedicalRecord.objects.all().order_by('-uploaded_at'),
                'error': 'No input found. Please upload or type a report.'
            })

        # Save initial record
        record = MedicalRecord.objects.create(
            patient_name=patient_name,
            report_text=report_text,
            insurance_summary="",
            markdown_summary=""
        )

        # Generate summary and markdown
        summary_insurance, markdown_summary = summarize_and_convert(report_text, record.id)
        summary_insurance = summary_insurance.replace("<n>", "\n")
        markdown_summary = markdown_summary.replace("<n>", "\n")

        # Remove any prompt/instruction lines
        summary_insurance = remove_prompt_lines(summary_insurance)

        # Save updated summaries
        record.insurance_summary = summary_insurance
        record.markdown_summary = markdown_summary
        record.save()

        # Pass to insurance module
        request.session['insurance_query'] = summary_insurance
        request.session.modified = True

        return redirect('insurance:query')

    # GET request
    records = MedicalRecord.objects.all().order_by('-uploaded_at')
    return render(request, 'index.html', {'records': records})


def download_markdown(request, record_id):
    file_path = f"downloads/record_{record_id}.md"
    if os.path.exists(file_path):
        return FileResponse(open(file_path, 'rb'), as_attachment=True, filename=f"record_{record_id}.md")
    else:
        raise Http404("Markdown file not found.")


def delete_all_summaries(request):
    if request.method == 'POST':
        MedicalRecord.objects.all().delete()

        # Clean up markdown files
        download_dir = "downloads"
        if os.path.exists(download_dir):
            for filename in os.listdir(download_dir):
                if filename.endswith(".md"):
                    os.remove(os.path.join(download_dir, filename))

        messages.success(request, "All summaries deleted.")
        return redirect('index')
    else:
        raise Http404("Invalid request method.")
