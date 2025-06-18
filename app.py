from flask import Flask
from app.routes import main_bp, assets_bp
from app.database import init_db

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(assets_bp)
    
    # Initialize database
    with app.app_context():
        init_db()
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
