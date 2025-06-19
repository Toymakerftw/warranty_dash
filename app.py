from flask import Flask
from app.routes import main_bp, assets_bp
from app.database import init_db, get_app_setting
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

def create_app():
    app = Flask(__name__)
    app.config.from_object('config.Config')
    
    # Register blueprints
    app.register_blueprint(main_bp)
    app.register_blueprint(assets_bp)
    
    # Initialize database and scheduler inside app context
    with app.app_context():
        init_db()
        if not hasattr(app, 'apscheduler'):
            from app.routes.main import send_scheduled_alerts
            scheduler = BackgroundScheduler()
            # Load cron from DB if present
            cron_expr = get_app_setting('alert_cron', app.config.get('ALERT_CRON', '0 8 * * *'))
            cron_parts = cron_expr.split()
            scheduler.add_job(
                send_scheduled_alerts,
                'cron',
                args=[app],
                minute=cron_parts[0],
                hour=cron_parts[1],
                day=cron_parts[2],
                month=cron_parts[3],
                day_of_week=cron_parts[4],
                id='send_scheduled_alerts',
                replace_existing=True
            )
            scheduler.start()
            atexit.register(lambda: scheduler.shutdown())
            app.apscheduler = scheduler
    
    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)