#####################################################################################
# This email feature will be discontinued as calendly supports auto email confirmations. PIN will be sent in chat and in calendly invite.
#####################################################################################
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib
from dotenv import load_dotenv

load_dotenv()

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


async def send_pin_email(
    to_email: str,
    patient_name: str,
    appointment_id: str,
    pin: str,
    slot: str,
) -> None:
    """
    Send the appointment confirmation email containing the PIN.
    The PIN is only ever delivered via this email — never via chat.
    """
    subject = "Your Acme Dental Appointment Confirmation & PIN"
    body = f"""Hello {patient_name},

Your appointment at Acme Dental has been confirmed.

  Appointment ID : {appointment_id}
  Date & Time    : {slot}

Your security PIN is: {pin}

You will need this PIN to cancel or reschedule your appointment.
Keep it safe — do not share it with anyone.

If you did not book this appointment, please call us immediately at (555) 123-4567.

See you soon,
Acme Dental Team
"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_FROM
    msg["To"] = to_email
    msg.attach(MIMEText(body, "plain"))

    await aiosmtplib.send(
        msg,
        hostname=SMTP_HOST,
        port=SMTP_PORT,
        username=SMTP_USER,
        password=SMTP_PASSWORD,
        start_tls=True,
    )
