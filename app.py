from flask import Flask, request, jsonify
import openai
import shopify
import os
from dotenv import load_dotenv

app = Flask(__name__)
load_dotenv()

# Initialize OpenAI and Shopify
openai.api_key = os.getenv('OPENAI_API_KEY')
shop_url = os.getenv('SHOPIFY_SHOP_URL')
access_token = os.getenv('SHOPIFY_ACCESS_TOKEN')

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "healthy"}), 200

@app.route('/process-email', methods=['POST'])
def process_email():
    data = request.json
    
    if not data or 'email_body' not in data:
        return jsonify({"error": "Missing email body"}), 400
        
    try:
        # Basic email classification
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a customer service specialist. Classify the following email into one of these categories: order_status, return_request, product_info, shipping_info, or other."
                },
                {
                    "role": "user",
                    "content": data['email_body']
                }
            ]
        )
        
        email_type = response.choices[0].message.content.strip().lower()
        
        # Generate response based on type
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful, friendly customer service representative. Generate a response to the customer's email."
                },
                {
                    "role": "user",
                    "content": f"Email type: {email_type}\nCustomer email: {data['email_body']}"
                }
            ]
        )
        
        generated_response = response.choices[0].message.content
        
        return jsonify({
            "type": email_type,
            "response": generated_response
        })
        
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)))
