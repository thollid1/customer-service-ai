import os
import pickle
import base64
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import openai
import shopify
from flask import Flask, request, jsonify
from email.mime.text import MIMEText
from datetime import datetime

app = Flask(__name__)

# Debug print of environment variables
print("SHOPIFY_SHOP_URL:", os.getenv('SHOPIFY_SHOP_URL'))
print("Has access token:", bool(os.getenv('SHOPIFY_ACCESS_TOKEN')))

# Initialize OpenAI and Shopify
openai.api_key = os.getenv('OPENAI_API_KEY')
shop_url = os.getenv('SHOPIFY_SHOP_URL')
shopify.Session.setup(api_key=os.getenv('SHOPIFY_ACCESS_TOKEN'))
session = shopify.Session(shop_url, '2023-01', os.getenv('SHOPIFY_ACCESS_TOKEN'))
shopify.ShopifyResource.activate_session(session)

# Gmail API setup
SCOPES = ['https://www.googleapis.com/auth/gmail.modify',
          'https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    """Get or refresh Gmail credentials."""
    creds = None
    if os.path.exists('.credentials/token.pickle'):
        with open('.credentials/token.pickle', 'rb') as token:
            creds = pickle.load(token)
    
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Get credentials from environment variable
            creds_json = os.getenv('GOOGLE_CREDENTIALS')
            if not creds_json:
                raise ValueError("Google credentials not found in environment variables")
            
            # Write credentials temporarily to file
            with open('temp_client_secrets.json', 'w') as f:
                f.write(creds_json)
            
            flow = InstalledAppFlow.from_client_secrets_file(
                'temp_client_secrets.json', SCOPES)
            creds = flow.run_local_server(port=0)
            
            # Clean up temporary file
            os.remove('temp_client_secrets.json')
        
        # Save the credentials for future use
        os.makedirs('.credentials', exist_ok=True)
        with open('.credentials/token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def get_order_by_email(email):
    """Search for orders by customer email."""
    try:
        orders = shopify.Order.find(email=email)
        if orders:
            return orders[0]  # Return most recent order
        return None
    except Exception as e:
        print(f"Error finding order by email: {e}")
        return None

def get_order_by_number(order_number):
    """Get order by order number."""
    try:
        print(f"Attempting to find order: {order_number}")  # Debug log
        order = shopify.Order.find(order_number)
        print(f"Order found: {order.id if order else 'None'}")  # Debug log
        return order
    except Exception as e:
        print(f"Error finding order by number: {e}")
        return None

def create_email_response(to_email, subject, message_body):
    """Create email message."""
    message = MIMEText(message_body)
    message['to'] = to_email
    message['from'] = 'support@yallneedjesus.co'
    message['subject'] = f"Re: {subject}"
    return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

def get_order_details(order):
    """Extract relevant order details."""
    if not order:
        return None
    
    details = {
        'order_number': order.name,
        'status': order.fulfillment_status or 'unfulfilled',
        'created_at': order.created_at,
        'items': [],
        'tracking_info': None,
        'shipping_address': {},
        'total_price': str(order.total_price),
        'financial_status': order.financial_status
    }
    
    # Add line items
    for item in order.line_items:
        details['items'].append({
            'title': item.title,
            'quantity': item.quantity,
            'variant_title': item.variant_title,
            'sku': item.sku
        })
    
    # Add shipping address if available
    if order.shipping_address:
        details['shipping_address'] = {
            'address1': order.shipping_address.address1,
            'address2': order.shipping_address.address2,
            'city': order.shipping_address.city,
            'province': order.shipping_address.province,
            'zip': order.shipping_address.zip,
            'country': order.shipping_address.country
        }
    
    # Add tracking if available
    if order.fulfillments:
        latest_fulfillment = order.fulfillments[0]
        if latest_fulfillment.tracking_number:
            details['tracking_info'] = {
                'number': latest_fulfillment.tracking_number,
                'company': latest_fulfillment.tracking_company,
                'url': latest_fulfillment.tracking_url
            }
    
    return details

def generate_response(customer_email, message_text, order_details=None):
    """Generate appropriate response using OpenAI."""
    system_prompt = """You are a customer service representative for Y'all Need Jesus Co.
    Key Information:
    - We're a small business with high demand
    - Pre-orders take 13-18 business days (19-25 calendar days)
    - We're actively working to improve shipping times
    - Be friendly, professional, and understanding
    - Always include specific order details when available
    - If tracking is available, always include tracking number and carrier
    - Sign off with 'Best regards, Y'all Need Jesus Co. Customer Care'"""
    
    if order_details:
        system_prompt += f"\n\nOrder Details:\n{json.dumps(order_details, indent=2)}"
    else:
        system_prompt += "\n\nNo order found for this customer. Ask for order number or email used for purchase."
    
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message_text}
        ]
    )
    
    return response.choices[0].message['content']

@app.route('/process-email', methods=['POST'])
def process_email():
    try:
        data = request.json
        customer_email = data.get('from')
        message_text = data.get('message')
        subject = data.get('subject')
        
        print(f"Processing email from: {customer_email}")  # Debug log
        
        # Look for order number in message
        import re
        order_number_match = re.search(r'#(\d+)', message_text)
        order_details = None
        
        if order_number_match:
            # Try to find order by number
            print(f"Found order number: {order_number_match.group(1)}")  # Debug log
            order = get_order_by_number(order_number_match.group(1))
            if order:
                order_details = get_order_details(order)
        else:
            # Try to find order by email
            print(f"Searching by email: {customer_email}")  # Debug log
            order = get_order_by_email(customer_email)
            if order:
                order_details = get_order_details(order)
        
        # Generate response
        response_text = generate_response(customer_email, message_text, order_details)
        
        # Create and send email
        service = get_gmail_service()
        email_message = create_email_response(customer_email, subject, response_text)
        service.users().messages().send(userId='me', body=email_message).execute()
        
        return jsonify({"status": "success", "response": response_text})
        
    except Exception as e:
        print(f"Error processing email: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/test', methods=['GET'])
def test():
    """Test endpoint to verify the service is running."""
    return jsonify({"status": "healthy"})

@app.route('/test-order', methods=['GET'])
def test_order():
    """Test endpoint to verify Shopify integration."""
    try:
        # Debug information
        shop = shopify.Shop.current()
        
        # Try multiple ways to find the order
        test_order_numbers = ['3239', '#3239', '003239']
        
        for order_num in test_order_numbers:
            try:
                print(f"Attempting to find order with: {order_num}")
                order = shopify.Order.find(order_num)
                if order:
                    details = get_order_details(order)
                    return jsonify({
                        "status": "success", 
                        "order_details": details,
                        "shop_name": shop.name,
                        "found_with": order_num
                    })
            except Exception as e:
                print(f"Failed with {order_num}: {str(e)}")
        
        # If we get here, no order was found
        # Let's try to get a list of recent orders
        orders = shopify.Order.find(limit=5)
        recent_order_numbers = [order.name for order in orders]
        
        return jsonify({
            "status": "error", 
            "message": "Order not found",
            "shop_name": shop.name,
            "shop_url": os.getenv('SHOPIFY_SHOP_URL'),
            "recent_orders": recent_order_numbers
        })
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "message": str(e),
            "shop_url": os.getenv('SHOPIFY_SHOP_URL')
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
