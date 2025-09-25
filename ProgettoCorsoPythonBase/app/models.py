# app/models.py
from . import db
from datetime import datetime

#         STUDENT
class Student(db.Model):
    __tablename__ = "students"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=True)
    corso = db.Column(db.String(120), nullable=False)
    programmi = db.Column(db.String(500), nullable=True)
    immagine_profilo = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    
    
    strikes = db.Column(db.Integer, default=0)            
    mute_until = db.Column(db.DateTime, nullable=True)      
    is_shadow_banned = db.Column(db.Boolean, default=False) 

    
    posts = db.relationship(
        "Post",
        backref="author",
        lazy=True,
        cascade="all, delete-orphan"
    )
    likes = db.relationship(
        "Like",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment",
        backref="user",
        lazy=True,
        cascade="all, delete-orphan"
    )
    reports = db.relationship(  
        "Report",
        backref="reporter",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Student id={self.id} nome={self.nome} email={self.email}>"

class Post(db.Model):
    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True
    )
    content = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    video_url = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    moderation_status = db.Column(db.String(20), default="approved", index=True)
    toxicity_score = db.Column(db.Float, default=0.0)
    is_visible = db.Column(db.Boolean, default=True, index=True)

    # --- Relazioni ---
    likes = db.relationship(
        "Like",
        backref="post",
        lazy=True,
        cascade="all, delete-orphan"
    )
    comments = db.relationship(
        "Comment",
        backref="post",
        lazy=True,
        cascade="all, delete-orphan"
    )
    reports = db.relationship(
        "Report",
        backref="post",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Post id={self.id} author_id={self.author_id}>"

   
    def to_dict(self):
        return {
            "id": self.id,
            "author_id": self.author_id,
            "author_nome": self.author.nome if self.author else None,
            "content": self.content,
            "image_url": self.image_url,
            "video_url": self.video_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "likes_count": len(self.likes),
            "comments_count": len(self.comments),
            "moderation_status": self.moderation_status,
            "toxicity_score": self.toxicity_score,
            "is_visible": self.is_visible,
        }

#          LIKE

class Like(db.Model):
    __tablename__ = "likes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False,
        index=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint("user_id", "post_id", name="uq_like_user_post"),
    )

    def __repr__(self):
        return f"<Like user_id={self.user_id} post_id={self.post_id}>"


#        COMMENT

class Comment(db.Model):
    __tablename__ = "comments"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=False,
        index=True
    )
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    
    moderation_status = db.Column(db.String(20), default="approved", index=True)
    toxicity_score = db.Column(db.Float, default=0.0)
    is_visible = db.Column(db.Boolean, default=True, index=True)

    reports = db.relationship(
        "Report",
        backref="comment",
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Comment id={self.id} post_id={self.post_id} user_id={self.user_id}>"

#         REPORT

class Report(db.Model):
    """
    Segnalazione di un contenuto da parte di un utente.
    Può riferirsi a un Post OPPURE a un Comment (uno solo dei due).
    """
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    reporter_id = db.Column(
        db.Integer,
        db.ForeignKey("students.id"),
        nullable=False,
        index=True
    )
    post_id = db.Column(
        db.Integer,
        db.ForeignKey("posts.id"),
        nullable=True,
        index=True
    )
    comment_id = db.Column(
        db.Integer,
        db.ForeignKey("comments.id"),
        nullable=True,
        index=True
    )
    reason = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    handled = db.Column(db.Boolean, default=False, index=True)

    def __repr__(self):
        target = f"post_id={self.post_id}" if self.post_id else f"comment_id={self.comment_id}"
        return f"<Report id={self.id} reporter_id={self.reporter_id} {target} handled={self.handled}>"
