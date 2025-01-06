from flask import Flask, request, jsonify, render_template_string
import openai
import shopify
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

app = Flask(__name__)
load_dotenv()

# Initialize OpenAI and Shopify
openai.api_key = os.getenv('OPENAI_API_KEY')
shop_url = os.getenv('SHOPIFY_SHOP_URL')
access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Customer Service Email Tester</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 0 20px; }
        textarea { width: 100%; height: 150px; margin: 10px 0; }
        input[type="text"] { width: 100%; margin: 10px 0; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        #response { margin-top: 20px; white-space: pre-wrap; }
    </style>
</head>
<body>
    <h1>Customer Service Email Tester</h1>
    <div>
        <label>Order ID (optional):</label>
        <input type="text" id="orderId" placeholder="Enter order ID...">
        
        <label>Customer Email:</label>
        <textarea id="emailBody" placeholder="Enter customer email..."></textarea>
        
        <button onclick="sendEmail()">Test Response</button>
    </div>
    <div id="response"></div>

    <script>
        async function sendEmail() {
            try {
                const emailBody = document.getElementById('emailBody').value;
                const orderId = document.getElementById('orderId').value;
                
                const response = await fetch('/process-email', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email_body: emailBody,
                        order_id: orderId || null
                    }),
                });
                
                const data = await response.json();
                console.log('Response data:', data);  // Debug log
                
                if (data.error) {
                    document.getElementById('response').innerText = "Error: " + data.error;
                } else {
                    document.getElementById('response').innerText = data.response || "No response generated";
                }
            } catch (error) {
                console.error('Error:', error);  // Debug log
                document.getElementById('response').innerText = "Error: " + error.message;
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)
