"""Email service for sending vote receipts."""
from flask import current_app, render_template_string
from flask_mail import Message
from app import mail


# HTML email template for vote receipts
RECEIPT_EMAIL_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="margin: 0; padding: 0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f5f7fa;">
    <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
        <!-- Header -->
        <div style="background: linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%); border-radius: 16px 16px 0 0; padding: 30px; text-align: center;">
            <h1 style="color: white; margin: 0; font-size: 24px;">Online Voting Nepal</h1>
            <p style="color: rgba(255,255,255,0.8); margin: 10px 0 0 0; font-size: 14px;">Your Vote Receipt</p>
        </div>

        <!-- Body -->
        <div style="background: white; padding: 30px; border-radius: 0 0 16px 16px; box-shadow: 0 4px 20px rgba(0,0,0,0.1);">
            <!-- Success Icon -->
            <div style="text-align: center; margin-bottom: 20px;">
                <div style="width: 60px; height: 60px; background: #d1fae5; border-radius: 50%; display: inline-flex; align-items: center; justify-content: center;">
                    <span style="font-size: 30px; color: #10b981;">&#10003;</span>
                </div>
            </div>

            <h2 style="color: #047857; text-align: center; margin: 0 0 10px 0;">Vote Successfully Recorded!</h2>
            <p style="color: #64748b; text-align: center; margin: 0 0 25px 0;">
                Your vote for <strong style="color: #1a202c;">{{ election_name }}</strong> has been securely recorded.
            </p>

            <!-- Receipt Box -->
            <div style="background: #fefce8; border: 2px solid #fde047; border-radius: 12px; padding: 20px; margin-bottom: 20px;">
                <h3 style="color: #854d0e; margin: 0 0 15px 0; font-size: 16px;">
                    Your Vote Receipt
                </h3>

                <div style="background: white; border: 1px solid #fde047; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                    <p style="color: #92400e; font-size: 11px; font-weight: 600; text-transform: uppercase; margin: 0 0 5px 0;">
                        Receipt ID (Both FPTP & PR Ballots)
                    </p>
                    <code style="background: #fef9c3; padding: 8px 12px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 16px; font-weight: 600; color: #713f12; display: block; letter-spacing: 1px;">
                        {{ receipt_id }}
                    </code>
                </div>

                {% if timestamp %}
                <div style="background: #ecfdf5; border: 1px solid #6ee7b7; border-radius: 8px; padding: 12px;">
                    <p style="color: #047857; font-size: 11px; font-weight: 600; text-transform: uppercase; margin: 0 0 5px 0;">
                        Recorded At
                    </p>
                    <code style="background: #d1fae5; padding: 8px 12px; border-radius: 6px; font-family: 'Courier New', monospace; font-size: 14px; font-weight: 600; color: #065f46; display: block;">
                        {{ timestamp }}
                    </code>
                </div>
                {% endif %}
            </div>

            <!-- Verification Info -->
            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 10px; padding: 15px; margin-bottom: 20px;">
                <h4 style="color: #1e3a8a; margin: 0 0 8px 0; font-size: 14px;">How to Verify Your Vote</h4>
                <p style="color: #1e40af; font-size: 13px; margin: 0; line-height: 1.5;">
                    Visit our verification page and enter your receipt ID to confirm both your FPTP and PR votes were recorded.
                    Your actual vote choices remain encrypted and anonymous.
                </p>
            </div>

            <!-- Important Notice -->
            <div style="background: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 12px;">
                <p style="color: #991b1b; font-size: 12px; margin: 0; line-height: 1.5;">
                    <strong>Important:</strong> Keep this receipt ID safe. It is your proof that your votes were recorded.
                    Do not share it with anyone to protect your voting privacy.
                </p>
            </div>

            <!-- Footer -->
            <div style="text-align: center; margin-top: 25px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                <p style="color: #64748b; font-size: 13px; margin: 0;">
                    Thank you for participating in the democratic process.
                </p>
                <p style="color: #94a3b8; font-size: 12px; margin: 10px 0 0 0;">
                    Online Voting Nepal &copy; 2024
                </p>
            </div>
        </div>
    </div>
</body>
</html>
"""


def send_receipt_email(to_email: str, election_name: str,
                       receipt_id: str = None, timestamp: str = None) -> dict:
    """Send vote receipt email to the voter.

    Args:
        to_email: Recipient email address
        election_name: Name of the election
        receipt_id: Combined receipt ID for both FPTP and PR ballots
        timestamp: Vote timestamp string

    Returns:
        dict with success status and message
    """
    # Check if email is enabled
    if not current_app.config.get('MAIL_ENABLED'):
        return {
            'success': False,
            'message': 'Email service is not configured. Please contact the administrator.'
        }

    if not receipt_id:
        return {
            'success': False,
            'message': 'No receipt provided to send.'
        }

    try:
        # Render the HTML email
        html_body = render_template_string(
            RECEIPT_EMAIL_TEMPLATE,
            election_name=election_name,
            receipt_id=receipt_id,
            timestamp=timestamp
        )

        # Create the message
        msg = Message(
            subject=f"Your Vote Receipt - {election_name}",
            recipients=[to_email],
            html=html_body,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER')
        )

        # Send the email
        mail.send(msg)

        return {
            'success': True,
            'message': f'Receipt sent successfully to {to_email}'
        }

    except Exception as e:
        current_app.logger.error(f"Failed to send receipt email: {str(e)}")
        return {
            'success': False,
            'message': 'Failed to send email. Please try again later.'
        }


def is_email_enabled() -> bool:
    """Check if email service is enabled and configured."""
    return current_app.config.get('MAIL_ENABLED', False)
