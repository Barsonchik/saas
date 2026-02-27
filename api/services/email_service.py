import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from api.config import Config


def _send_email(to_email: str, subject: str, html: str):
    if not Config.SMTP_HOST or not to_email:
        return False

    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = Config.SMTP_USERNAME or 'noreply@shadowsocks.local'
    msg['To'] = to_email
    msg.attach(MIMEText(html, 'html', 'utf-8'))

    with smtplib.SMTP(Config.SMTP_HOST, Config.SMTP_PORT, timeout=20) as server:
        if Config.SMTP_USE_TLS:
            server.starttls()
        if Config.SMTP_USERNAME and Config.SMTP_PASSWORD:
            server.login(Config.SMTP_USERNAME, Config.SMTP_PASSWORD)
        server.sendmail(msg['From'], [to_email], msg.as_string())
    return True


def send_welcome_email(email, username, server, port, password, method, expires_days):
    html = f"""
    <h2>Welcome, {username}</h2>
    <p>Your Shadowsocks profile is ready:</p>
    <ul>
      <li>Server: {server}</li>
      <li>Port: {port}</li>
      <li>Password: {password}</li>
      <li>Method: {method}</li>
      <li>Duration: {expires_days} days</li>
    </ul>
    """
    return _send_email(email, 'Shadowsocks access details', html)


def send_expiration_email(email, username, days_left, expires_at):
    html = f"<p>User <b>{username}</b> expires in <b>{days_left}</b> days ({expires_at}).</p>"
    return _send_email(email, 'Shadowsocks expiration warning', html)


def send_traffic_warning_email(email, username, usage_percent, traffic_used_gb, traffic_limit_gb):
    html = (
        f"<p>User <b>{username}</b> used <b>{usage_percent:.1f}%</b> traffic "
        f"({traffic_used_gb} / {traffic_limit_gb} GB).</p>"
    )
    return _send_email(email, 'Shadowsocks traffic warning', html)


def send_expired_email(email, username):
    html = f"<p>User <b>{username}</b> is expired and disabled automatically.</p>"
    return _send_email(email, 'Shadowsocks user expired', html)
