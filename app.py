from flask import Flask, request, jsonify, render_template_string
import openai
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Initialize OpenAI
openai.api_key = os.getenv('OPENAI_API_KEY')

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Customer Service Email Tester</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 0 20px; }
        textarea { width: 100%; height: 150px; margin: 10px 0; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        #response { margin-top: 20px; white-space: pre-wrap; background: #f8f9fa; padding: 15px; border-radius: 5px; }
        .error { color: #dc3545; }
        label { display: block; margin-top: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Customer Service Email Tester</h1>
    <div>
        <label>Customer Email:</label>
        <textarea id="emailBody" placeholder="Enter customer email..."></textarea>
        <button onclick="sendEmail()">Test Response</button>
    </div>
    <div id="response"></div>

    <script>
        async function sendEmail() {
            try {
                const emailBody = document.getElementById('emailBody').value;
                if (!emailBody.trim()) {
                    document.getElementById('response').innerHTML = '<span class="error">Please enter an email message</span>';
                    return;
                }
                
                document.getElementById('response').innerText = 'Processing...';
                
                const response = await fetch('/process-email', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        email_body: emailBody
                    }),
                });
                
                const data = await response.json();
                if (data.error) {
                    document.getElementById('response').innerHTML = '<span class="error">Error: ' + data.error + '</span>';
                } else {
                    document.getElementById('response').innerText = data.response;
                }
            } catch (error) {
                document.getElementById('response').innerHTML = '<span class="error">Error: ' + error.message + '</span>';
            }
        }
    </script>
</body>
</html>
"""

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/process-email', methods=['POST'])
def process_email():
    try:
        data = request.json
        
        if not data or 'email_body' not in data:
            return jsonify({"error": "Please provide an email message."}), 400
            
        print("Processing email:", data['email_body'])  # Debug log
        
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """You are a helpful customer service representative for Y'all Need Jesus Co.
                    Key Information:
                    - We're a small business with high demand
                    - Pre-orders take 13-18 business days (19-25 calendar days)
                    - We're actively working to improve shipping times
                    - Be friendly, professional, and understanding
                    - If it's a pre-order question, always include shipping timeframe
                    - Sign off with 'Best regards, Y'all Need Jesus Co. Customer Care'"""
                },
                {
                    "role": "user",
                    "content": data['email_body']
                }
            ]
        )
        
        return jsonify({
            "response": response.choices[0].message['content']
        })
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return jsonify({"error": f"Error processing request: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
