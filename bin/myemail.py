#!/usr/bin/env python3
import smtplib, ssl
# https://stackoverflow.com/questions/3362600/how-to-send-email-attachments
from os.path import basename
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import COMMASPACE, formatdate
import os
import sys

import argparse
parser = argparse.ArgumentParser(prog='myemail', description='Python-Based Email Sender')
parser.add_argument('--body', type=str, nargs=1, required=True, help='Message Body')
parser.add_argument('--subject', type=str, nargs=1, required=True, help="Message Subject")
parser.add_argument('--send-from', type=str, nargs=1, required=True, help="Sender")
parser.add_argument('--send-to', type=str, nargs=1, required=True, help="Comma-delimited recipients")
parser.add_argument('--attachments', type=str, nargs='+', help='Attachments')
parser.add_argument('--port', type=int, nargs=1, default=int(os.environ.get("RELAY_PORT","587")), help='The port to use for sending')
parser.add_argument('--relay', type=str, nargs=1, default=os.environ.get("RELAY","relay.somewhere"), help='The relay server to use')
pres=parser.parse_args(sys.argv[1:])

smtp_server = pres.relay
smtp_port = pres.port
send_from = pres.send_from[0]
subject = pres.subject[0]
recipients = pres.send_to[0].split(",")
attachments = []
if pres.attachments is not None:
    attachments = pres.attachments
body = pres.body[0]
with open(body,"r") as fd:
    msg_text = fd.read()

print("Using relay:", smtp_server)
print("Using port:", smtp_port)

context = ssl.create_default_context()
def SendMail(send_from = send_from, send_to = None, subject = None, text = "", files=[]): 
    assert type(send_to) == list
    assert type(subject) == str
    assert type(send_from) == str
    assert type(text) == str
    assert type(files) == list
    with smtplib.SMTP(host=smtp_server,port=smtp_port) as server:
        server.ehlo()  # Can be omitted
        server.starttls(context=context)
        server.ehlo()  # Can be omitted
    
        msg = MIMEMultipart()
        msg['From'] = send_from
        msg['To'] = COMMASPACE.join(send_to)
        msg['Date'] = formatdate(localtime=True)
        msg['Subject'] = subject
    
        msg.attach(MIMEText(text))
    
        for f in files or []:
            with open(f, "rb") as fil:
                part = MIMEApplication(
                    fil.read(),
                    Name=basename(f)
                )
            # After the file is closed
            part['Content-Disposition'] = 'attachment; filename="%s"' % basename(f)
            msg.attach(part)
    
        server.sendmail(send_from, send_to, msg.as_string())
        server.quit()

if __name__ == "__main__":
    SendMail(send_to=recipients,subject=subject,files=attachments,text=msg_text)
