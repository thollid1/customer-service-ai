from flask import Flask, request, jsonify, render_template_string
import openai
import os
from dotenv import load_dotenv
import shopify
from datetime import datetime

app = Flask(__name__)
load_dotenv()

# Initialize OpenAI and Shopify
openai.api_key = os.getenv('OPENAI_API_KEY')
shop_url = os.getenv('SHOPIFY_SHOP_URL')
shopify.Session.setup(api_key=os.getenv('SHOPIFY_ACCESS_TOKEN'))
session = shopify.Session(shop_url, '2023-01', os.getenv('SHOPIFY_ACCESS_TOKEN'))
shopify.ShopifyResource.activate_session(session)

def get_detailed_order_info(order_id):
    try:
        print(f"Fetching order: {order_id}")  # Debug log
        order = shopify.Order.find(order_id)
        print(f"Found order: {order.name}")  # Debug log
        
        # Basic Order Info
        order_info = {
            'order_number': order.name,
            'email': order.email,
            'order_date': order.created_at,
            'fulfillment_status': order.fulfillment_status or 'unfulfilled',
            'financial_status': order.financial_status,
            'items': [],
            'tracking': []
        }

        # Line Items
        for item in order.line_items:
            order_info['items'].append({
                'title': item.title,
                'quantity': item.quantity,
                'sku': item.sku,
                'price': str(item.price)
            })

        # Tracking Information
        if order.fulfillments:
            print(f"Found fulfillments: {len(order.fulfillments)}")  # Debug log
            for fulfillment in order.fulfillments:
                if fulfillment.tracking_number:
                    order_info['tracking'].append({
                        'number': fulfillment.tracking_number,
                        'url': fulfillment.tracking_url,
                        'carrier': fulfillment.tracking_company
                    })
                    print(f"Added tracking: {fulfillment.tracking_number}")  # Debug log

        return order_info
    except Exception as e:
        print(f"Error fetching order details: {e}")
        return None

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Customer Service Email Tester</title>
    <style>
        body { font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 0 20px; }
        textarea { width: 100%; height: 150px; margin: 10px 0; }
        input { width: 100%; margin: 10px 0; padding: 8px; }
        button { padding: 10px 20px; background: #007bff; color: white; border: none; cursor: pointer; }
        #response { margin-top: 20px; white-space: pre-wrap; background: #f8f9fa; padding: 15px; border-radius: 5px; }
        .error { color: #dc3545; }
        label { display: block; margin-top: 10px; font-weight: bold; }
    </style>
</head>
<body>
    <h1>Customer Service Email Tester</h1>
    <div>
        <label>Order Number:</label>
        <input type="text" id="orderId" placeholder="Enter order number (e.g., 3239)">
        
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
                        email_body: emailBody,
                        order_id: orderId
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
        order_info = None
        
        if not data or 'email_body' not in data:
            return jsonify({"error": "Please provide an email message."}), 400
        
        # Fetch order details if order ID is provided
        if data.get('order_id'):
            print(f"Fetching order details for: {data['order_id']}")  # Debug log
            order_info = get_detailed_order_info(data['order_id'])
            print(f"Order info retrieved: {order_info}")  # Debug log

        # Construct the system prompt
        system_prompt = """You are a helpful customer service representative for Y'all Need Jesus Co.
            Key Information:
            - We're a small business with high demand
            - Pre-orders take 13-18 business days (19-25 calendar days)
            - We're actively working to improve shipping times
            - Be friendly, professional, and understanding
            - Always include tracking information if available
            - Sign off with 'Best regards, Y'all Need Jesus Co. Customer Care'
            """

        # Add order details to the prompt if available
        if order_info:
            system_prompt += "\nOrder Details:\n"
            system_prompt += f"Order Number: {order_info['order_number']}\n"
            system_prompt += f"Status: {order_info['fulfillment_status']}\n"
            
            if order_info['tracking']:
                tracking = order_info['tracking'][0]  # Get first tracking info
                system_prompt += f"Tracking Number: {tracking['number']}\n"
                system_prompt += f"Carrier: {tracking['carrier']}\n"
                system_prompt += f"Tracking URL: {tracking['url']}\n"
            
            print(f"Final system prompt: {system_prompt}")  # Debug log

        # Generate response using OpenAI
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
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
