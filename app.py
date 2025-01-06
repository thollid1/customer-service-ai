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
        order = shopify.Order.find(order_id)
        
        # Basic Order Info
        order_info = {
            'order_number': order.name,
            'customer_email': order.email,
            'order_date': order.created_at,
            'status': {
                'fulfillment_status': order.fulfillment_status or 'unfulfilled',
                'financial_status': order.financial_status,
                'order_status': order.status
            },
            'customer': {
                'first_name': order.customer.first_name if order.customer else None,
                'last_name': order.customer.last_name if order.customer else None,
                'email': order.customer.email if order.customer else None
            },
            'shipping_address': {
                'address1': order.shipping_address.address1 if order.shipping_address else None,
                'address2': order.shipping_address.address2 if order.shipping_address else None,
                'city': order.shipping_address.city if order.shipping_address else None,
                'province': order.shipping_address.province if order.shipping_address else None,
                'zip': order.shipping_address.zip if order.shipping_address else None,
                'country': order.shipping_address.country if order.shipping_address else None
            },
            'billing_address': {
                'address1': order.billing_address.address1 if order.billing_address else None,
                'address2': order.billing_address.address2 if order.billing_address else None,
                'city': order.billing_address.city if order.billing_address else None,
                'province': order.billing_address.province if order.billing_address else None,
                'zip': order.billing_address.zip if order.billing_address else None,
                'country': order.billing_address.country if order.billing_address else None
            },
            'line_items': [],
            'shipping_info': {
                'method': order.shipping_lines[0].title if order.shipping_lines else None,
                'cost': str(order.total_shipping_price_set.shop_money.amount) if order.total_shipping_price_set else '0.00'
            },
            'payment_info': {
                'gateway': order.gateway,
                'total_price': str(order.total_price),
                'subtotal': str(order.subtotal_price),
                'total_tax': str(order.total_tax),
                'currency': order.currency
            },
            'discounts': [],
            'notes': order.note,
            'tags': order.tags,
            'tracking_info': []
        }

        # Line Items
        for item in order.line_items:
            line_item = {
                'title': item.title,
                'quantity': item.quantity,
                'sku': item.sku,
                'price': str(item.price),
                'variant_title': item.variant_title,
                'product_id': item.product_id,
                'variant_id': item.variant_id,
                'properties': item.properties if hasattr(item, 'properties') else None
            }
            order_info['line_items'].append(line_item)

        # Tracking Information
        if order.fulfillments:
            for fulfillment in order.fulfillments:
                tracking_info = {
                    'tracking_number': fulfillment.tracking_number,
                    'tracking_url': fulfillment.tracking_url,
                    'carrier': fulfillment.tracking_company,
                    'status': fulfillment.status,
                    'created_at': fulfillment.created_at
                }
                order_info['tracking_info'].append(tracking_info)

        # Discounts
        if order.discount_codes:
            for discount in order.discount_codes:
                discount_info = {
                    'code': discount.code,
                    'amount': str(discount.amount),
                    'type': discount.type
                }
                order_info['discounts'].append(discount_info)

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
        order_details = None
        
        if data.get('order_id'):
            order_details = get_detailed_order_info(data['order_id'])
        
        if not data or 'email_body' not in data:
            return jsonify({"error": "Please provide an email message."}), 400
            
        system_prompt = """You are a helpful customer service representative for Y'all Need Jesus Co.
            Key Information:
            - We're a small business with high demand
            - Pre-orders take 13-18 business days (19-25 calendar days)
            - We're actively working to improve shipping times
            - Be friendly, professional, and understanding
            - If it's a pre-order question, always include shipping timeframe
            - Sign off with 'Best regards, Y'all Need Jesus Co. Customer Care'
            """
            
        if order_details:
            system_prompt += f"\nOrder Details:\n{order_details}"

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
