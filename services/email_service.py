import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime
from services.i18n import t

class EmailService:
    def __init__(self, db):
        self.db = db

    def _get_smtp_config(self):
        """Preia setarile SMTP din baza de date."""
        try:
            rows = self.db.conn.execute("SELECT key, value FROM settings").fetchall()
            conf = {row['key']: row['value'] for row in rows}
            return conf
        except:
            return {}

    def send_email(self, trip_id, recipient, subject, body, attachment_path=None):
        conf = self._get_smtp_config()
        if not conf.get('smtp_user') or not conf.get('smtp_password'):
            raise Exception(t("email.config_missing"))

        msg = MIMEMultipart()
        msg['From'] = conf.get('smtp_user')
        msg['To'] = recipient
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))

        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, "rb") as f:
                part = MIMEApplication(f.read(), Name=os.path.basename(attachment_path))
                part['Content-Disposition'] = f'attachment; filename="{os.path.basename(attachment_path)}"'
                msg.attach(part)

        try:
            # TLS connection (Port 587)
            server = smtplib.SMTP(conf['smtp_server'], int(conf['smtp_port']))
            server.starttls()
            server.login(conf['smtp_user'], conf['smtp_password'])
            server.send_message(msg)
            server.quit()
            
            # Log succes in baza de date
            self.db.add_email_log(trip_id, recipient, subject, "Success")
            return True
        except Exception as e:
            self.db.add_email_log(trip_id, recipient, subject, "Failed", str(e))
            raise e

    def get_template(self, type, data):
        """Returneaza subiectul si corpul e-mailului bazat pe tip."""
        if type == "invoice":
            subj = t("email.invoice_subject").format(data.get('invoice_number', ''), data.get('company_name', ''))
            amount = float(data.get('amount', 0))
            body = t("email.invoice_body").format(data.get('invoice_number', ''), amount, data.get('due_date', ''), data.get('company_name', ''))
        elif type == "reminder":
            subj = t("email.reminder_subject").format(data.get('invoice_number', ''))
            amount = float(data.get('amount', 0))
            body = t("email.reminder_body").format(data.get('invoice_number', ''), amount, data.get('due_date', ''), data.get('company_name', ''))
        else:
            subj = t("email.default_subject")
            body = t("email.default_body")
        return subj, body