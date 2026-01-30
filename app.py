import requests
import os
# Example static game list (title, platform, market values by condition)
PRICECHARTING_API_KEY = os.environ.get('PRICECHARTING_API_KEY', 'YOUR_API_KEY_HERE')

from flask import Flask, render_template, request, redirect, url_for, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_admin import Admin
from flask_admin.contrib.sqla import ModelView
import os



app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///games.db'
app.config['SECRET_KEY'] = 'your_secret_key_here'
db = SQLAlchemy(app)



class GameSubmission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), nullable=False)
    game_title = db.Column(db.String(100), nullable=False)
    platform = db.Column(db.String(50), nullable=False)
    condition = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Float, nullable=False)
    notes = db.Column(db.Text, nullable=True)

# Remove template_mode argument for compatibility with installed Flask-Admin
admin = Admin(app, name='Game Submissions')
admin.add_view(ModelView(GameSubmission, db.session))



@app.route('/')
def index():
    return render_template('index.html')
# API endpoint to search PriceCharting for games
@app.route('/api/search')
def api_search():
    q = request.args.get('q', '')
    print(f"[DEBUG] API key: {PRICECHARTING_API_KEY}")
    print(f"[DEBUG] Search query: {q}")
    if not q:
        print("[DEBUG] No query provided.")
        return jsonify({'results': []})
    url = f'https://www.pricecharting.com/api/products?t={PRICECHARTING_API_KEY}&q={q}'
    print(f"[DEBUG] Requesting URL: {url}")
    try:
        resp = requests.get(url)
        print(f"[DEBUG] Response status: {resp.status_code}")
        data = resp.json()
        print(f"[DEBUG] Response JSON: {data}")
        results = []
        for product in data.get('products', []):
            results.append({
                'title': product.get('product-name', ''),
                'platform': product.get('console-name', ''),
                'prices': {
                    'Loose': float(product.get('loose-price', 0)),
                    'Complete': float(product.get('complete-price', 0)),
                    'Sealed': float(product.get('new-price', 0)),
                }
            })
        return jsonify({'results': results})
    except Exception as e:
        print(f"[DEBUG] Exception: {e}")
        return jsonify({'results': [], 'error': str(e)})


# API endpoint to get live market prices from PriceCharting
@app.route('/api/pricecharting')
def pricecharting():
    title = request.args.get('title', '')
    platform = request.args.get('platform', '')
    if not title or not platform:
        return jsonify({'error': 'Missing title or platform'}), 400
    # PriceCharting API expects platform in a specific format, may need mapping
    # Example: https://www.pricecharting.com/api/product?t=API_KEY&q=Super+Mario+64&console=nintendo-64
    url = f'https://www.pricecharting.com/api/product?t={PRICECHARTING_API_KEY}&q={title}&console={platform}'
    try:
        resp = requests.get(url)
        data = resp.json()
        if 'product' in data:
            product = data['product']
            prices = {
                'Loose': float(product.get('loose-price', 0)),
                'Complete': float(product.get('complete-price', 0)),
                'Sealed': float(product.get('new-price', 0)),
            }
            return jsonify({'prices': prices, 'title': product.get('product-name', title)})
        else:
            return jsonify({'error': 'Not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/sell', methods=['GET', 'POST'])
def sell():
    title = request.args.get('title', '')
    platform = request.args.get('platform', '')
    if request.method == 'POST':
        submission = GameSubmission(
            name=request.form['name'],
            email=request.form['email'],
            game_title=request.form['game_title'],
            platform=request.form['platform'],
            condition=request.form['condition'],
            price=float(request.form['price']),
            notes=request.form.get('notes', '')
        )
        db.session.add(submission)
        db.session.commit()
        return redirect(url_for('index'))
    return f'''
        <h2>Sell Your Game</h2>
        <form method="post">
            Name: <input type="text" name="name" required><br>
            Email: <input type="email" name="email" required><br>
            Game Title: <input type="text" name="game_title" value="{title}" required><br>
            Platform: <input type="text" name="platform" value="{platform}" required><br>
            Condition: <input type="radio" name="condition" value="Sealed" required> Sealed
            <input type="radio" name="condition" value="Complete"> Complete
            <input type="radio" name="condition" value="Loose"> Loose<br>
            <label>What We Pay: </label> <span id="what_we_pay">(select condition)</span><br>
            Price: <input type="number" step="0.01" name="price" required><br>
            Notes: <textarea name="notes"></textarea><br>
            <input type="submit" value="Submit">
        </form>
        <script>
        // Fetch live price from backend
        function fetchPrice() {{
            const title = document.getElementsByName('game_title')[0].value;
            const platform = document.getElementsByName('platform')[0].value;
            fetch(`/api/pricecharting?title=${encodeURIComponent(title)}&platform=${encodeURIComponent(platform)}`)
                .then(r => r.json())
                .then(data => {{
                    window._livePrices = data.prices || {{}};
                }});
        }}
        document.getElementsByName('game_title')[0].addEventListener('blur', fetchPrice);
        document.getElementsByName('platform')[0].addEventListener('blur', fetchPrice);
        document.querySelectorAll('input[name="condition"]').forEach(function(radio) {{
            radio.addEventListener('change', function() {{
                const cond = this.value;
                const prices = window._livePrices || {{}};
                let pay = prices[cond] ? (prices[cond]*0.6).toFixed(2) : '';
                document.getElementById('what_we_pay').innerText = pay ? ('$' + pay + ' (' + cond + ')') : '(no price)';
                if (pay) document.getElementsByName('price')[0].value = pay;
            }});
        }});
        </script>
    '''

if __name__ == '__main__':
    if not os.path.exists('games.db'):
        with app.app_context():
            db.create_all()
    app.run(debug=True)
