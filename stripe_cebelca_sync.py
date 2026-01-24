import os
import stripe
import requests
import json
from flask import Flask, request, jsonify
from dotenv import load_dotenv

# Debugging path
# print(f"DEBUG: CWD is {os.getcwd()}") # Removed debug print
env_path = os.path.join(os.path.dirname(__file__), '.env')
# print(f"DEBUG: Looking for .env at {env_path}") # Removed debug print
# print(f"DEBUG: .env exists? {os.path.exists(env_path)}") # Removed debug print

load_dotenv(dotenv_path=env_path)

# Configuration
STRIPE_API_KEY = os.getenv('STRIPE_API_KEY', '').strip()
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '').strip()
CEBELCA_API_KEY = os.getenv('CEBELCA_API_KEY', '').strip()
CEBELCA_APP_NAME = os.getenv('CEBELCA_APP_NAME', 'StripeSync').strip()

# Initialize Stripe
stripe.api_key = STRIPE_API_KEY

app = Flask(__name__)

class CebelcaClient:
    API_URL = "https://www.cebelca.biz/API"

    def __init__(self, api_key):
        self.api_key = api_key

    def _request(self, resource, method, data=None):
        if data is None:
            data = {}
        
        # Cebelca expects parameters in the query string for _r and _m
        # and the data as form-urlencoded body.
        # But wait, the python library example sends:
        # url: https://.../API?_r=...&_m=...
        # body: ...
        
        params = {
            '_r': resource,
            '_m': method
        }
        
        # Requests handles Basic Auth and URL encoding
        try:
            response = requests.post(
                self.API_URL,
                params=params,
                auth=(self.api_key, 'x'),
                data=data
            )
            response.raise_for_status()
            
            # Cebelca often returns JSON without explicit header, or sometimes text/plain
            # We try to parse JSON
            try:
                return response.json()
            except ValueError:
                return response.text
                
        except requests.exceptions.RequestException as e:
            print(f"Error calling Cebelca API [{resource}.{method}]: {e}")
            if e.response is not None:
                print(f"Response: {e.response.text}")
            raise

    def assure_partner(self, name, email, street=None, city=None, postal=None, vat_id=None):
        """
        Ensures a partner exists in Cebelca. 
        Returns the list of matching partners (usually one).
        """
        payload = {
            'name': name,
            'email': email
        }
        if street: payload['street'] = street
        if city: payload['city'] = city
        if postal: payload['postal'] = postal
        if vat_id: payload['vatid'] = vat_id
        
        if CEBELCA_APP_NAME:
            payload['notes'] = f"Synced via {CEBELCA_APP_NAME}"

        # 'assure' method creates or updates
        return self._request('partner', 'assure', payload)

    def create_invoice_head(self, partner_id, date_sent, date_to_pay, date_served, id_document_ext=None, title=None):
        """
        Creates the invoice header using insert-smart-2.
        """
        payload = {
            'id_partner': partner_id,
            'date_sent': date_sent,    # dd.mm.yyyy
            'date_to_pay': date_to_pay, # dd.mm.yyyy
            'date_served': date_served, # dd.mm.yyyy
            'id_currency': 2, # EUR? Adjust if needed
            'conv_rate': 0,
            'doctype': 0
        }
        if id_document_ext:
            payload['id_document_ext'] = id_document_ext
        
        if title:
            payload['title'] = title 
        
        return self._request('invoice-sent', 'insert-smart-2', payload)

    def add_line_item(self, invoice_id, title, quantity, price, vat_rate, mu='pcs'):
        """
        Adds a line item to the invoice.
        """
        payload = {
            'id_invoice_sent': invoice_id,
            'title': title,
            'qty': quantity,
            'mu': mu,
            'price': price, # Price per unit
            'vat': vat_rate, # Percentage, e.g. 22
            'discount': 0
        }
        return self._request('invoice-sent-b', 'insert-into', payload)

    def finalize_invoice(self, invoice_id):
        """
        Optional: Mark invoice as issued/fiscalize.
        Note: Use with caution as this might be irreversible.
        """
        # Uncomment if you want to automatically issue the invoice
        # return self._request('invoice-sent', 'issue', {'id': invoice_id})
        pass

cebelca = CebelcaClient(CEBELCA_API_KEY)

@app.route('/webhook', methods=['POST'])
def webhook():
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, STRIPE_WEBHOOK_SECRET
        )
    except ValueError:
        # Invalid payload
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        # Invalid signature
        return jsonify({'error': 'Invalid signature'}), 400

    # Handle the event
    if event['type'] == 'invoice.payment_succeeded':
        invoice = event['data']['object']
        handle_checkout_session(invoice)

    return jsonify({'status': 'success'}), 200

def handle_checkout_session(invoice):
    print(f"Processing invoice {invoice['id']}")
    
    # 1. Extract Customer Info
    customer_name = invoice.get('customer_name') or invoice.get('customer_email') or "Unknown Customer"
    customer_email = invoice.get('customer_email')
    
    address = invoice.get('customer_address') or {}
    street = address.get('line1', '')
    city = address.get('city', '')
    postal = address.get('postal_code', '')
    
    vat_id = None
    # if invoice.get('customer_tax_ids'):
    #      # If tax IDs are expanded or available in the object
    #      # This logic depends on Stripe API version and expansion
    #      pass

    # 2. Sync Partner to Cebelca
    try:
        partner_response = cebelca.assure_partner(
            name=customer_name,
            email=customer_email,
            street=street,
            city=city,
            postal=postal,
            vat_id=vat_id
        )

        # assure returns a list of results, e.g. [[{'id': 68, ...}]]
        if isinstance(partner_response, list) and len(partner_response) > 0:
            first_match = partner_response[0]
            if isinstance(first_match, list) and len(first_match) > 0:
                 # Nested list case
                 partner_id = first_match[0].get('id')
            elif isinstance(first_match, dict):
                 # Flat list case
                 partner_id = first_match.get('id')
            else:
                 print(f"Unexpected partner item type: {type(first_match)}")
                 partner_id = None
        else:
            # Fallback if structure is different
            print(f"Unexpected partner response structure: {partner_response}")
            return # Abort
        
        if not partner_id:
             print("Could not extract partner ID")
             return

        print(f"Partner synced: ID {partner_id}")

        # 3. Create Invoice Header
        # Convert timestamp to dd.mm.yyyy
        from datetime import datetime
        date_sent = datetime.fromtimestamp(invoice['created']).strftime('%d.%m.%Y')
        date_due = datetime.fromtimestamp(invoice['due_date'] or invoice['created']).strftime('%d.%m.%Y')
        date_served = date_sent # Assuming served on creation for now

        # Use Stripe invoice number as reference
        stripe_invoice_number = invoice.get('number')
        
        invoice_response = cebelca.create_invoice_head(
            partner_id=partner_id,
            date_sent=date_sent,
            date_to_pay=date_due,
            date_served=date_served,
            id_document_ext=stripe_invoice_number,
            title=stripe_invoice_number
        )
        
        # The response is a nested list: [[{'id': 123}]]
        if isinstance(invoice_response, list) and len(invoice_response) > 0:
            first_item = invoice_response[0]
            if isinstance(first_item, list) and len(first_item) > 0:
                cebelca_invoice_id = first_item[0].get('id')
            elif isinstance(first_item, dict):
                 cebelca_invoice_id = first_item.get('id')
            else:
                 print(f"Unexpected response structure item: {first_item}")
                 return
        else:
             print(f"Failed to create invoice header: {invoice_response}")
             return

        print(f"Invoice header created: ID {cebelca_invoice_id}")

        # 4. Add Line Items
        # TODO: Uncomment this when ready to test line items
        # for line in invoice['lines']['data']:
        #     description = line.get('description', 'Item')
        #     qty = line.get('quantity', 1)
        #     # Stripe amounts are in cents
        #     unit_amount = line.get('price', {}).get('unit_amount', 0) / 100.0
        #
        #     # Extract VAT rate
        #     vat_rate = 0
        #     if line.get('tax_rates'):
        #         # Assuming simple single tax rate
        #         vat_rate = line['tax_rates'][0].get('percentage', 0)
        #     elif line.get('tax_amounts'):
        #          # Calculate from tax amounts if needed
        #          pass
        #
        #     cebelca.add_line_item(
        #         invoice_id=cebelca_invoice_id,
        #         title=description,
        #         quantity=qty,
        #         price=unit_amount,
        #         vat_rate=vat_rate
        #     )

        print(f"Draft invoice created in Cebelca. Invoice ID: {cebelca_invoice_id}")
        print(f"Stripe invoice: {stripe_invoice_number}")

    except Exception as e:
        print(f"Error syncing invoice: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting server on port {port}")
    app.run(host='0.0.0.0', port=port)
