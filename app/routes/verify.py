from flask import Blueprint, render_template, request, jsonify
from app.models.vote import Vote

verify_bp = Blueprint('verify', __name__)


@verify_bp.route('/verify', methods=['GET', 'POST'])
def verify_receipt():
    """Public page to verify a vote receipt."""
    result = None
    receipt_id = None

    if request.method == 'POST':
        receipt_id = request.form.get('receipt_id', '').strip().upper()

        if not receipt_id:
            result = {
                'valid': False,
                'message': 'Please enter a receipt ID.'
            }
        elif not receipt_id.startswith('RCP-'):
            result = {
                'valid': False,
                'message': 'Invalid receipt format. Receipt IDs start with "RCP-".'
            }
        else:
            result = Vote.verify_receipt(receipt_id)

    return render_template('verify/verify_receipt.html',
                           result=result,
                           receipt_id=receipt_id)


@verify_bp.route('/verify/api', methods=['POST'])
def verify_receipt_api():
    """API endpoint for receipt verification."""
    data = request.get_json()

    if not data or 'receipt_id' not in data:
        return jsonify({
            'valid': False,
            'message': 'Receipt ID is required.'
        }), 400

    receipt_id = data['receipt_id'].strip().upper()

    if not receipt_id.startswith('RCP-'):
        return jsonify({
            'valid': False,
            'message': 'Invalid receipt format.'
        }), 400

    result = Vote.verify_receipt(receipt_id)
    return jsonify(result)
