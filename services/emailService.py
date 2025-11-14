import sib_api_v3_sdk
from sib_api_v3_sdk.rest import ApiException
from pprint import pprint
from dotenv import load_dotenv
import os

load_dotenv()

html_format = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Your Login Credentials</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: #f5f5f5;
            padding: 20px;
            min-height: 100vh;
        }
        
        .container {
            max-width: 600px;
            margin: 0 auto;
            background: #ffffff;
            border-radius: 8px;
            overflow: hidden;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
        }
        
        .header {
            background: #000000;
            padding: 40px 20px;
            text-align: center;
            border-bottom: 3px solid #333333;
        }
        
        .header h1 {
            color: #ffffff;
            font-size: 28px;
            font-weight: 700;
            letter-spacing: 0.5px;
        }
        
        .header p {
            color: #cccccc;
            font-size: 14px;
            margin-top: 8px;
        }
        
        .content {
            padding: 40px 30px;
        }
        
        .greeting {
            font-size: 18px;
            color: #000000;
            margin-bottom: 20px;
            font-weight: 600;
        }
        
        .message {
            font-size: 14px;
            color: #333333;
            line-height: 1.6;
            margin-bottom: 30px;
        }
        
        .credentials-box {
            background: #f9f9f9;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 30px;
            margin-bottom: 30px;
            border-left: 4px solid #000000;
        }
        
        .credential-item {
            margin-bottom: 25px;
        }
        
        .credential-item:last-child {
            margin-bottom: 0;
        }
        
        .credential-label {
            font-size: 12px;
            font-weight: 700;
            color: #000000;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 8px;
            display: block;
        }
        
        .credential-value {
            font-size: 16px;
            color: #000000;
            background: #ffffff;
            padding: 12px 15px;
            border-radius: 6px;
            word-break: break-all;
            font-family: 'Courier New', monospace;
            font-weight: 600;
            border: 1px solid #d0d0d0;
        }
        
        .warning-box {
            background: #fff8f0;
            border-left: 4px solid #000000;
            padding: 15px;
            border-radius: 6px;
            margin-bottom: 30px;
        }
        
        .warning-box p {
            font-size: 13px;
            color: #333333;
            margin: 0;
            line-height: 1.5;
        }
        
        .warning-box strong {
            color: #000000;
        }
        
        .cta-button {
            display: inline-block;
            background: #000000;
            color: #ffffff;
            padding: 14px 40px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            font-size: 15px;
            text-align: center;
            width: 100%;
            margin-bottom: 20px;
            box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            border: none;
            cursor: pointer;
            transition: background 0.3s;
        }
        
        .cta-button:hover {
            background: #333333;
        }
        
        .steps {
            background: #f9f9f9;
            padding: 25px;
            border-radius: 6px;
            margin-bottom: 30px;
            border: 1px solid #e0e0e0;
        }
        
        .steps-title {
            font-size: 14px;
            font-weight: 700;
            color: #000000;
            margin-bottom: 15px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }
        
        .step {
            display: flex;
            margin-bottom: 12px;
            font-size: 13px;
            color: #333333;
            line-height: 1.6;
        }
        
        .step-number {
            background: #000000;
            color: #ffffff;
            width: 24px;
            height: 24px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: 700;
            margin-right: 12px;
            flex-shrink: 0;
            font-size: 12px;
        }
        
        .footer {
            background: #f5f5f5;
            padding: 30px;
            text-align: center;
            border-top: 1px solid #e0e0e0;
        }
        
        .footer-text {
            font-size: 12px;
            color: #666666;
            line-height: 1.6;
            margin: 0;
        }
        
        .footer-text a {
            color: #000000;
            text-decoration: none;
            font-weight: 600;
        }
        
        .footer-text a:hover {
            text-decoration: underline;
        }
        
        @media (max-width: 600px) {
            .container {
                border-radius: 0;
            }
            
            .header {
                padding: 30px 20px;
            }
            
            .header h1 {
                font-size: 24px;
            }
            
            .content {
                padding: 25px 20px;
            }
            
            .credentials-box {
                padding: 20px;
            }
            
            .credential-value {
                font-size: 14px;
            }
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>Login Credentials</h1>
            <p>Your secure access information</p>
        </div>
        
        <!-- Content -->
        <div class="content">
            <div class="greeting">Welcome to Your Account</div>
            
            <p class="message">
                Your account has been successfully created. Below are your login credentials to access your account. Please keep this information secure and confidential.
            </p>
            
            <!-- Credentials -->
            <div class="credentials-box">
                <div class="credential-item">
                    <span class="credential-label">Username</span>
                    <div class="credential-value">{username}</div>
                </div>
                
                <div class="credential-item">
                    <span class="credential-label">Password</span>
                    <div class="credential-value">SecurePass123!@#</div>
                </div>
            </div>
            
            <!-- Warning -->
            <div class="warning-box">
                <p>
                    <strong>Security Notice:</strong> Do not share your password with anyone. We will never ask for your password via email.
                </p>
            </div>
            
            <!-- Quick Steps -->
            <div class="steps">
                <div class="steps-title">Getting Started</div>
                <div class="step">
                    <div class="step-number">1</div>
                    <div>Visit our login page</div>
                </div>
                <div class="step">
                    <div class="step-number">2</div>
                    <div>Enter your username or email address</div>
                </div>
                <div class="step">
                    <div class="step-number">3</div>
                    <div>Enter your password and click login</div>
                </div>
                <div class="step">
                    <div class="step-number">4</div>
                    <div>Change your password on your first login</div>
                </div>
            </div>
            
            <!-- CTA Button -->
            <a href="#" class="cta-button">Go to Login Page</a>
            
            <p class="message" style="text-align: center; font-size: 12px; color: #666666; margin-bottom: 0;">
                If you did not create this account, please contact our support team immediately.
            </p>
        </div>
        
        <!-- Footer -->
        <div class="footer">
            <p class="footer-text">
                Copyright © 2025 Your Company. All rights reserved.<br>
                Need help? <a href="#">Contact Support</a>
            </p>
        </div>
    </div>
</body>
</html>
"""

html_format = html_format.replace("{username}","Gaurav")

def sendEmail(receiver,subject):
    
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.getenv("BREV_API_KEY")
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": f"{receiver}", "name": "Gaurav Shetty"}],
        sender={"email": "gauravshetty4452@gmail.com", "name": "Gaurav"},
        subject=subject,
        html_content=html_format
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        pprint(api_response)
    except ApiException as e:
        print("Exception when sending transactional email: %s\n" % e)


otp_html_template = """
<!DOCTYPE html>
<html>
<head>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f4f4f4; margin: 0; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; background-color: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .header { text-align: center; margin-bottom: 30px; }
        .otp-box { background-color: #f8f9fa; border: 2px solid #007bff; border-radius: 8px; padding: 20px; text-align: center; margin: 20px 0; }
        .otp-code { font-size: 32px; font-weight: bold; color: #007bff; letter-spacing: 5px; margin: 10px 0; }
        .footer { margin-top: 30px; text-align: center; color: #666; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Email Verification</h1>
            <p>Please verify your email address to complete registration</p>
        </div>
        
        <div class="otp-box">
            <h2>Your Verification Code</h2>
            <div class="otp-code">{otp}</div>
            <p>This code will expire in 10 minutes</p>
        </div>
        
        <p>Enter this code in the verification form to activate your account.</p>
        <p>If you didn't request this verification, please ignore this email.</p>
        
        <div class="footer">
            <p>This is an automated message, please do not reply.</p>
        </div>
    </div>
</body>
</html>
"""

def sendOTPEmail(receiver, otp):
    configuration = sib_api_v3_sdk.Configuration()
    configuration.api_key['api-key'] = os.getenv("BREV_API_KEY")
    api_instance = sib_api_v3_sdk.TransactionalEmailsApi(sib_api_v3_sdk.ApiClient(configuration))

    html_content = otp_html_template.replace("{otp}", otp)
    
    send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
        to=[{"email": receiver, "name": "User"}],
        sender={"email": "gauravshetty4452@gmail.com", "name": "Your App"},
        subject="Email Verification - OTP Code",
        html_content=html_content
    )

    try:
        api_response = api_instance.send_transac_email(send_smtp_email)
        print(f"OTP email sent successfully to {receiver}")
        return True
    except ApiException as e:
        print(f"Exception when sending OTP email: {e}")
        return False