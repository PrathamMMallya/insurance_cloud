from django.db import models

class MedicalRecord(models.Model):
    patient_name = models.CharField(max_length=100)
    report_text = models.TextField()
    summary_doctor = models.TextField()   #  summary 1 for insurance/doctor..
    summary_patient = models.TextField()  # Simplified summary for patient...
    markdown_summary = models.TextField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.patient_name
