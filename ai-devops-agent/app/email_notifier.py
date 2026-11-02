import os
import ssl
import smtplib
from email.message import EmailMessage


def send_email(subject, body):
    sender = os.environ["SMTP_FROM"]
    recipient = os.environ["SMTP_TO"]
    password = os.environ["SMTP_APP_PASSWORD"].replace(" ", "")

    message = EmailMessage()
    message["From"] = sender
    message["To"] = recipient
    message["Subject"] = subject
    message.set_content(body)

    with smtplib.SMTP(
        os.environ["SMTP_HOST"],
        int(os.environ["SMTP_PORT"]),
        timeout=20,
    ) as smtp:
        smtp.ehlo()
        smtp.starttls(context=ssl.create_default_context())
        smtp.ehlo()
        smtp.login(sender, password)
        smtp.send_message(message)

    print("Email sent successfully.")
