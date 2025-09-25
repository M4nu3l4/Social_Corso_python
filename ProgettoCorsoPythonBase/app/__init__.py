from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from .extensions import limiter

db = SQLAlchemy()
migrate = Migrate()

def create_app():
    app = Flask(__name__, instance_relative_config=True)
    limiter.init_app(app)


    app.config.from_object("config.Config")

    
    db.init_app(app)
    migrate.init_app(app, db)
   
    

    
    from .routes import bp as main_bp
    app.register_blueprint(main_bp)

    
    @app.cli.command("init-db")
    def init_db():
        from . import models  
        with app.app_context():
            db.create_all()
            print("Database creato in instance/social.db")

    # CLI
    @app.cli.command("seed")
    def seed():
        from .models import Student, Post
        s = Student(nome="Mario Rossi", email="mario@example.com", corso="Python Base",
                    programmi="php, react, angular")
        db.session.add(s)
        db.session.flush()
        p = Post(author_id=s.id, content="Ciao a tutti, primo post sul social!")
        db.session.add(p)
        db.session.commit()
        print("Dati di seed inseriti.")
    return app

