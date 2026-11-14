"""Daily email digest via Gmail SMTP. Reads .run/summary.json written by main.py.

Needs env vars GMAIL_USER, GMAIL_APP_PASSWORD, DIGEST_TO (GitHub Secrets). Sends nothing on days with no new postings.
"""
import html
import json
import os
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path

SUMMARY = Path(__file__).parent / ".run" / "summary.json"
ORDER = ["food", "pharma", "adjacent"]


def compose(summary, board_url):
    new, failed = summary["new"], summary.get("failed", [])
    text, parts = [], []
    for industry in ORDER + sorted({p["industry"] for p in new} - set(ORDER)):
        group = [p for p in new if p["industry"] == industry]
        if not group:
            continue
        text.append(f"\n{industry.upper()} ({len(group)})")
        parts.append(f"<h3 style='margin:18px 0 6px'>{industry.title()} ({len(group)})</h3><ul style='padding-left:18px'>")
        for p in group:
            text.append(f"- {p['company']}: {p['title']} | {p['location']} | {p['eligibility_flag']}\n  {p['url']}")
            parts.append(
                "<li style='margin-bottom:6px'><b>%s</b>: <a href='%s'>%s</a><br><span style='color:#555'>%s · %s</span></li>"
                % tuple(html.escape(str(x), quote=True) for x in
                        (p["company"], p["url"], p["title"], p["location"], p["eligibility_flag"])))
        parts.append("</ul>")
    text.append(f"\nBoard: {board_url}")
    parts.append(f"<p><a href='{html.escape(board_url, quote=True)}'>Open the board</a></p>")
    if failed:
        text.append("\nSources that failed today:\n" + "\n".join(f"- {f}" for f in failed))
        parts.append("<p style='color:#777;font-size:13px'>Sources that failed today:<br>"
                     + "<br>".join(html.escape(f) for f in failed) + "</p>")
    subject = f"{len(new)} new internship posting{'s' if len(new) != 1 else ''} ({summary['date']})"
    return subject, "\n".join(text).strip(), "<div style='font-family:sans-serif;font-size:15px'>%s</div>" % "".join(parts)


def main():
    if not SUMMARY.exists():
        print("no run summary found; nothing to send")
        return 0
    summary = json.loads(SUMMARY.read_text())
    if not summary["new"]:
        print("no new postings; skipping email")
        return 0
    user, password, to = (os.environ.get(k) for k in ("GMAIL_USER", "GMAIL_APP_PASSWORD", "DIGEST_TO"))
    if not (user and password and to):
        print("GMAIL_USER / GMAIL_APP_PASSWORD / DIGEST_TO not set; cannot send", file=sys.stderr)
        return 1
    subject, text, html_body = compose(summary, os.environ.get("BOARD_URL", ""))
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.set_content(text)
    msg.add_alternative(html_body, subtype="html")
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(user, password.replace(" ", ""))
        smtp.send_message(msg)
    print(f"sent: {subject}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
