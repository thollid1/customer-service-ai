from flask import Flask, request, jsonify
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

PRE_ORDER_MESSAGE = """
Our pre-orders typically ship within 13-18 business days. As a small business with high demand, we're working every day to improve our shipping times. We appreciate your patience and support!

Your order will be shipped as soon as possible within this timeframe. You'll receive a shipping confirmation email with tracking details once your order ships.
"""

def calculate_expected_delivery(order_date):
    """Calculate expected delivery window for pre-orders"""
    min_days = 19  # minimum calendar days
    max_days = 25  # maximum calendar days
    
    min_date = order_date + timedelta(days=min_days)
    max_date = order_date + timedelta(days=max_days)
    
    return min_date.strftime('%B %d'), max_date.strftime('%B %d')

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
