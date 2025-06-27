from transformers import PegasusTokenizer, PegasusForConditionalGeneration
import markdownify
import torch
import os

# Path to Pegasus model
model_path = r"C:\Users\tjsre\Desktop\projects\practice\ml\navy_project\secret\models\pegasus"

tokenizer = PegasusTokenizer.from_pretrained(model_path)
model = PegasusForConditionalGeneration.from_pretrained(model_path)
model.eval()

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
model.to(device)
# Generate summary from text + custom prompt
def generate_summary(text, prompt):
    input_text = prompt + "\n\n" + text.strip()
    inputs = tokenizer(input_text, truncation=True, padding="longest", return_tensors="pt").to(device)

    summary_ids = model.generate(
        **inputs,
        max_length=800,
        min_length=200,
        num_beams=5,
        length_penalty=1.0,
        early_stopping=True
    )
    return tokenizer.decode(summary_ids[0], skip_special_tokens=True)
    
def summarize_and_convert(text, record_id):
    markdown_version = markdownify.markdownify(text, heading_style="ATX")

    # Save markdown to disk
    os.makedirs("downloads", exist_ok=True)
    md_path = f"downloads/record_{record_id}.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(markdown_version)

    # 1. Doctor-oriented structured summary
    doctor_prompt = (
        "You are a helpful assistant. Extract the following from the patient's medical history:\n"
        "1. Age\n"
        "2. Health conditions (like asthma, thyroid, etc.)\n"
        "3. Budget or financial constraints with exact value (e.g. 15000rs)\n"
        "4. Desired coverage (e.g. doctor visits, prescriptions, etc.)"
    )
    summary_doctor = generate_summary(text, doctor_prompt)

    # 2. Patient-friendly simplified summary
    patient_prompt = (
        "Explain the patient's medical report in simple terms that a non-medical person can understand. "
        "Summarize the condition, what the patient should know, and any action they need to take."
    )
    summary_patient = generate_summary(text, patient_prompt)

    return summary_doctor, summary_patient, markdown_version
