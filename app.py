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
            const emailBody = document.getElementById('emailBody').value;
            const orderId = document.getElementById('orderId').value;
            
            const response = await fetch('/process-email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email_body: emailBody,
                    order_id: orderId
                }),
            });
            
            const data = await response.json();
            document.getElementById('response').innerText = data.response;
        }
    </script>
</body>
</html>
"""

PRE_ORDER_MESSAGE = """
Our pre-orders typically ship within 13-18 business days (19-25 calendar days). As a small business with high demand, we're working every day to improve our shipping times. We appreciate your patience and support!

Your order will be shipped as soon as possible within this timeframe. You'll receive a shipping confirmation email with tracking details once your order ships.
"""

def calculate_expected_delivery(order_date):
    """Calculate expected delivery window for pre-orders"""
    min_days = 19  # minimum calendar days
    max_days = 25  # maximum calendar days
    
    min_date = order_date + timedelta(days=min_days)
    max_date = order_date + timedelta(days=max_days)
    
    return min_date.strftime('%B %d'), max_date.strftime('%B %d')

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/process-email', methods=['POST'])
def process_email():
    data = request.json
    
    if not data or 'email_body' not in data:
        return jsonify({"error": "Missing email body"}), 400
        
    try:
        # First, classify the email type
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": """You are a customer service specialist for a small business with high demand.
                    Classify the following email into one of these categories:
                    - order_status (including pre-orders)
                    - return_request
                    - other"""
                },
                {
                    "role": "user",
                    "content": data['email_body']
                }
            ]
        )
        
        email_type = response.choices[0].message.content.strip().lower()
        
        # Build context based on email type
        context = {}
        if 'order_id' in data:
            try:
                order = shopify.Order.find(data['order_id'])
                context['order_status'] = order.fulfillment_status
                context['financial_status'] = order.financial_status
                context['created_at'] = order.created_at
                
                if order.fulfillment_status:
                    fulfillments = order.fulfillments()
                    if fulfillments:
                        context['tracking_number'] = fulfillments[0].tracking_number
                        context['tracking_url'] = fulfillments[0].tracking_url
                
                # Calculate delivery window for pre-orders
                order_date = datetime.strptime(order.created_at, "%Y-%m-%dT%H:%M:%S%z")
                min_date, max_date = calculate_expected_delivery(order_date)
                context['delivery_window'] = f"{min_date} - {max_date}"
            except:
                context['error'] = "Order not found"
        
        # Generate appropriate response
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": f"""You are a helpful, friendly customer service representative for a small business.
                    Key information:
                    - We're a small business with high demand
                    - Pre-orders take 13-18 business days (19-25 calendar days)
                    - We're actively working to improve shipping times
                    - Always be friendly and understanding
                    - For returns, ask for order number if not provided
                    
                    Context: {context}"""
                },
                {
                    "role": "user",
                    "content": f"Customer email: {data['email_body']}\nEmail type: {email_type}"
                }
            ]
        )
        
        generated_response = response.choices[0].message.content
        
        if email_type == 'order_status' and 'pre-order' in data['email_body'].lower():
            generated_response = f"{generated_response}\n\n{PRE_ORDER_MESSAGE}"
        
        return jsonify({
            "type": email_type,
            "response": generated_response,
            "context": context
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
