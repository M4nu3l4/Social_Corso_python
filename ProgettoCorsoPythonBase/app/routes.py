# app/routes.py
from flask import (
    Blueprint, request, jsonify, render_template,
    redirect, url_for, session, flash, current_app as app
)
from werkzeug.utils import secure_filename
from uuid import uuid4
from datetime import datetime, timedelta
from pathlib import Path
from sqlalchemy import or_
from . import db
from .models import Student, Post, Like, Comment, Report
from .moderation import assess
from .extensions import limiter

bp = Blueprint("main", __name__)

def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in app.config["ALLOWED_EXTENSIONS"]

def media_kind(filename: str):
    if "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[1].lower()
    if ext in app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        return "image"
    if ext in app.config["ALLOWED_VIDEO_EXTENSIONS"]:
        return "video"
    return None

def get_current_user() -> Student | None:
    uid = session.get("user_id")
    return Student.query.get(uid) if uid else None

def require_login():
    if not session.get("user_id"):
        flash("Devi essere registrato per questa azione.", "warning")
        return False
    return True

def require_owner(post: Post):
    uid = session.get("user_id")
    if not uid or uid != post.author_id:
        flash("Non sei autorizzato/a a modificare questo post.", "danger")
        return False
    return True

def require_comment_owner(comment: Comment):
    user = get_current_user()
    if not user:
        flash("Devi essere registrato per questa azione.", "warning")
        return False
    if user.id != comment.user_id and not can_moderate(user):
        flash("Non sei autorizzato/a a modificare questo commento.", "danger")
        return False
    return True

def is_muted(user: Student) -> bool:
    return bool(user and user.mute_until and user.mute_until > datetime.utcnow())

def can_moderate(user: Student | None) -> bool:
    admins = [e.lower() for e in app.config.get("ADMIN_EMAILS", [])]
    return bool(user and user.email and user.email.lower() in admins)

def escalate_strike(user: Student):
    user.strikes = (user.strikes or 0) + 1
    if user.strikes >= 3 and not is_muted(user):
        user.mute_until = datetime.utcnow() + timedelta(hours=24)

@bp.app_context_processor
def inject_globals():
    user = get_current_user()
    is_admin = can_moderate(user)
    if is_admin:
        pending_post_count = db.session.query(Post.id).filter(Post.moderation_status == "pending").count()
        pending_comment_count = db.session.query(Comment.id).filter(Comment.moderation_status == "pending").count()
    else:
        pending_post_count = 0
        pending_comment_count = 0
    return {
        "ctx_user": user,
        "is_admin": is_admin,
        "now": datetime.utcnow(),
        "pending_post_count": pending_post_count,
        "pending_comment_count": pending_comment_count,
        "pending_total": pending_post_count + pending_comment_count,
    }

@bp.get("/")
def root():
    return redirect(url_for("main.public_feed"))

@bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        nome = request.form.get("nome") or ""
        email = (request.form.get("email") or "").strip().lower() or None
        corso = request.form.get("corso") or ""
        programmi = request.form.get("programmi") or ""
        img = request.files.get("immagine_profilo")

        if not nome or not corso:
            flash("Nome e Corso sono obbligatori.", "danger")
            return render_template("register.html")

        existing = Student.query.filter_by(email=email).first() if email else None

        img_filename = None
        if img and img.filename:
            if not allowed_file(img.filename):
                flash("Formato immagine non valido. Usa png, jpg, jpeg, gif o webp.", "danger")
                return render_template("register.html")
            ext = img.filename.rsplit(".", 1)[1].lower()
            img_filename = f"{uuid4().hex}.{ext}"
            up_dir = Path(app.config["UPLOAD_FOLDER"])
            up_dir.mkdir(parents=True, exist_ok=True)
            save_path = up_dir / secure_filename(img_filename)
            img.save(save_path)
            img_filename = f"uploads/{img_filename}"

        if existing:
            if not existing.immagine_profilo and img_filename:
                existing.immagine_profilo = img_filename
                db.session.commit()
            session["user_id"] = existing.id
            flash(f"Accesso effettuato! Bentornata/o {existing.nome}.", "success")
            return redirect(url_for("main.public_feed"))

        s = Student(nome=nome, email=email, corso=corso, programmi=programmi, immagine_profilo=img_filename)
        db.session.add(s)
        db.session.commit()
        session["user_id"] = s.id
        flash("Registrazione completata! Benvenutə nel social del corso 👋", "success")
        return redirect(url_for("main.public_feed"))

    return render_template("register.html")

@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = (request.form.get("email") or "").strip().lower()
        if not email:
            flash("Inserisci la tua email.", "danger")
            return render_template("login.html")
        user = Student.query.filter_by(email=email).first()
        if not user:
            flash("Email non trovata. Registrati per creare un account.", "warning")
            return redirect(url_for("main.register"))
        session["user_id"] = user.id
        flash(f"Ciao {user.nome}, accesso effettuato ✅", "success")
        return redirect(url_for("main.public_feed"))
    return render_template("login.html")

@bp.route("/logout")
def logout():
    session.pop("user_id", None)
    flash("Logout effettuato.", "info")
    return redirect(url_for("main.public_feed"))

@bp.get("/feed")
def public_feed():
    user = get_current_user()
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return render_template("feed.html", posts=posts, current_user=user)

@bp.route("/me", methods=["GET"])
def my_feed():
    if not session.get("user_id"):
        flash("Per vedere la tua bacheca registrati o accedi.", "warning")
        return redirect(url_for("main.register"))
    me = Student.query.get(session["user_id"])
    posts = Post.query.filter_by(author_id=me.id).order_by(Post.created_at.desc()).all()
    return render_template("bacheca.html", me=me, posts=posts)

@bp.route("/post/create", methods=["POST"])
@limiter.limit("5 per 5 minutes")
def create_post_form():
    if not require_login():
        return redirect(url_for("main.register"))

    user = get_current_user()
    if is_muted(user):
        flash("Non puoi postare al momento (sei in mute temporaneo).", "danger")
        return redirect(url_for("main.public_feed"))

    content = (request.form.get("content") or "").strip() or None
    image_url = request.form.get("image_url") or None
    video_url = request.form.get("video_url") or None

    media = request.files.get("media_file")
    if media and media.filename:
        kind = media_kind(media.filename)
        if not kind:
            flash("Formato file non supportato. Immagini: png/jpg/jpeg/gif/webp. Video: mp4/webm/mov/avi/mkv.", "danger")
            return redirect(url_for("main.public_feed"))
        ext = media.filename.rsplit(".", 1)[1].lower()
        fname = f"{uuid4().hex}.{ext}"
        up_dir = Path(app.config["UPLOAD_FOLDER"])
        up_dir.mkdir(parents=True, exist_ok=True)
        save_path = up_dir / secure_filename(fname)
        media.save(save_path)
        rel_path = f"uploads/{fname}"
        if kind == "image":
            image_url = rel_path
            video_url = None
        else:
            video_url = rel_path
            image_url = None

    if not any([content, image_url, video_url]):
        flash("Inserisci almeno del testo, un'immagine o un video.", "danger")
        return redirect(url_for("main.public_feed"))

    mod = assess(content or "")
    status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
    status = status_map[mod.action]
    is_visible = (status == "approved") and (not user.is_shadow_banned)

    p = Post(
        author_id=user.id,
        content=content,
        image_url=image_url,
        video_url=video_url,
        moderation_status=status,
        toxicity_score=mod.score,
        is_visible=is_visible,
    )
    db.session.add(p)

    if mod.action == "reject":
        escalate_strike(user)
        flash("Il tuo post è stato rifiutato per linguaggio offensivo.", "danger")
    elif mod.action == "pending":
        flash("Il tuo post è in revisione.", "info")
    else:
        flash("Post pubblicato!", "success")

    db.session.commit()
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.route("/post/<int:post_id>/edit", methods=["GET", "POST"])
def edit_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not require_owner(post):
        return redirect(url_for("main.public_feed"))

    if request.method == "POST":
        content = (request.form.get("content") or "").strip() or None
        image_url = request.form.get("image_url") or None
        video_url = request.form.get("video_url") or None

        if not any([content, image_url, video_url]):
            flash("Il post non può essere vuoto. Inserisci testo, immagine o video.", "danger")
            return render_template("edit_post.html", post=post)

        mod = assess(content or "")
        status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
        status = status_map[mod.action]
        user = get_current_user()
        is_visible = (status == "approved") and (not (user and user.is_shadow_banned))

        post.content = content
        post.image_url = image_url
        post.video_url = video_url
        post.moderation_status = status
        post.toxicity_score = mod.score
        post.is_visible = is_visible

        if mod.action == "reject":
            escalate_strike(user)
            flash("Modifica rifiutata per linguaggio offensivo.", "danger")
        elif mod.action == "pending":
            flash("Modifica inviata: post in revisione.", "info")
        else:
            flash("Post aggiornato ✅", "success")

        db.session.commit()
        return redirect(url_for("main.public_feed"))

    return render_template("edit_post.html", post=post)

@bp.post("/post/<int:post_id>/delete")
def delete_post(post_id):
    post = Post.query.get_or_404(post_id)
    if not require_owner(post):
        return redirect(url_for("main.public_feed"))
    db.session.delete(post)
    db.session.commit()
    flash("Post eliminato 🗑️", "success")
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.post("/like/<int:post_id>")
def like_post_html(post_id):
    if not require_login():
        return redirect(url_for("main.register"))

    user_id = session["user_id"]
    post = Post.query.get_or_404(post_id)

    like = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if like:
        db.session.delete(like)
        db.session.commit()
        flash("Like rimosso.", "info")
    else:
        db.session.add(Like(user_id=user_id, post_id=post_id))
        try:
            db.session.commit()
            flash("Like aggiunto ❤️", "success")
        except Exception:
            db.session.rollback()
            flash("Hai già messo like a questo post.", "warning")

    return redirect(request.referrer or url_for("main.public_feed"))

@bp.post("/comment/<int:post_id>")
@limiter.limit("10 per 5 minutes")
def add_comment_html(post_id):
    if not require_login():
        return redirect(url_for("main.register"))

    user = get_current_user()
    if is_muted(user):
        flash("Non puoi commentare al momento (sei in mute temporaneo).", "danger")
        return redirect(url_for("main.public_feed"))

    body = (request.form.get("body") or "").strip()
    if not body:
        flash("Il commento non può essere vuoto.", "danger")
        return redirect(request.referrer or url_for("main.public_feed"))

    mod = assess(body)
    status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
    status = status_map[mod.action]
    is_visible = (status == "approved") and (not user.is_shadow_banned)

    c = Comment(
        user_id=user.id,
        post_id=post_id,
        body=body,
        moderation_status=status,
        toxicity_score=mod.score,
        is_visible=is_visible,
    )
    db.session.add(c)

    if mod.action == "reject":
        escalate_strike(user)
        flash("Commento rifiutato per linguaggio offensivo.", "danger")
    elif mod.action == "pending":
        flash("Commento in revisione.", "info")
    else:
        flash("Commento pubblicato.", "success")

    db.session.commit()
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.route("/comment/<int:comment_id>/edit", methods=["GET", "POST"])
def edit_comment(comment_id: int):
    c = Comment.query.get_or_404(comment_id)
    if not require_comment_owner(c):
        return redirect(url_for("main.public_feed"))

    if request.method == "POST":
        body = (request.form.get("body") or "").strip()
        if not body:
            flash("Il commento non può essere vuoto.", "danger")
            return redirect(request.referrer or url_for("main.public_feed"))

        mod = assess(body)
        status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
        status = status_map[mod.action]
        is_visible = (status == "approved") and (not c.user.is_shadow_banned)

        c.body = body
        c.moderation_status = status
        c.toxicity_score = mod.score
        c.is_visible = is_visible

        if mod.action == "reject":
            escalate_strike(c.user)
            flash("Modifica rifiutata per linguaggio offensivo.", "danger")
        elif mod.action == "pending":
            flash("Modifica inviata: commento in revisione.", "info")
        else:
            flash("Commento aggiornato ✅", "success")

        db.session.commit()
        return redirect(request.referrer or url_for("main.public_feed"))

    return render_template("edit_comment.html", comment=c)

@bp.post("/comment/<int:comment_id>/delete")
def delete_comment(comment_id: int):
    c = Comment.query.get_or_404(comment_id)
    if not require_comment_owner(c):
        return redirect(url_for("main.public_feed"))
    db.session.delete(c)
    db.session.commit()
    flash("Commento eliminato 🗑️", "success")
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.post("/report/post/<int:post_id>")
def report_post(post_id: int):
    if not require_login():
        return redirect(url_for("main.register"))
    reason = (request.form.get("reason") or "Segnalazione utente").strip()
    r = Report(reporter_id=session["user_id"], post_id=post_id, reason=reason)
    db.session.add(r)
    db.session.commit()
    flash("Grazie, la tua segnalazione è stata inviata.", "info")
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.post("/report/comment/<int:comment_id>")
def report_comment(comment_id: int):
    if not require_login():
        return redirect(url_for("main.register"))
    reason = (request.form.get("reason") or "Segnalazione utente").strip()
    r = Report(reporter_id=session["user_id"], comment_id=comment_id, reason=reason)
    db.session.add(r)
    db.session.commit()
    flash("Grazie, la tua segnalazione è stata inviata.", "info")
    return redirect(request.referrer or url_for("main.public_feed"))

@bp.get("/admin/moderation/pending")
def admin_pending_json():
    user = get_current_user()
    if not can_moderate(user):
        flash("Area riservata allo staff.", "danger")
        return redirect(url_for("main.public_feed"))

    posts = Post.query.filter(Post.moderation_status == "pending").order_by(Post.created_at.desc()).all()
    comments = Comment.query.filter(Comment.moderation_status == "pending").order_by(Comment.created_at.desc()).all()
    data = {
        "pending_posts": [p.to_dict() for p in posts],
        "pending_comments": [
            {
                "id": c.id,
                "post_id": c.post_id,
                "user_id": c.user_id,
                "body": c.body,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "toxicity_score": c.toxicity_score,
                "moderation_status": c.moderation_status,
                "is_visible": c.is_visible,
            }
            for c in comments
        ],
    }
    return jsonify(data)

@bp.get("/admin/moderation")
def admin_moderation_html():
    user = get_current_user()
    if not can_moderate(user):
        flash("Area riservata allo staff.", "danger")
        return redirect(url_for("main.public_feed"))

    pending_posts = Post.query.filter(Post.moderation_status == "pending").order_by(Post.created_at.desc()).all()
    pending_comments = Comment.query.filter(Comment.moderation_status == "pending").order_by(Comment.created_at.desc()).all()

    return render_template("admin_moderation.html", pending_posts=pending_posts, pending_comments=pending_comments)

def _admin_require():
    user = get_current_user()
    if not can_moderate(user):
        flash("Area riservata allo staff.", "danger")
        return False
    return True

@bp.post("/admin/moderation/post/<int:post_id>/approve")
def admin_approve_post(post_id: int):
    if not _admin_require():
        return redirect(url_for("main.public_feed"))
    post = Post.query.get_or_404(post_id)
    post.moderation_status = "approved"
    post.is_visible = not (post.author and post.author.is_shadow_banned)
    db.session.commit()
    flash("Post approvato.", "success")
    return redirect(request.referrer or url_for("main.admin_moderation_html"))

@bp.post("/admin/moderation/post/<int:post_id>/reject")
def admin_reject_post(post_id: int):
    if not _admin_require():
        return redirect(url_for("main.public_feed"))
    post = Post.query.get_or_404(post_id)
    post.moderation_status = "rejected"
    post.is_visible = False
    escalate_strike(post.author)
    db.session.commit()
    flash("Post rifiutato.", "warning")
    return redirect(request.referrer or url_for("main.admin_moderation_html"))

@bp.post("/admin/moderation/comment/<int:comment_id>/approve")
def admin_approve_comment(comment_id: int):
    if not _admin_require():
        return redirect(url_for("main.public_feed"))
    c = Comment.query.get_or_404(comment_id)
    c.moderation_status = "approved"
    c.is_visible = not (c.user and c.user.is_shadow_banned)
    db.session.commit()
    flash("Commento approvato.", "success")
    return redirect(request.referrer or url_for("main.admin_moderation_html"))

@bp.post("/admin/moderation/comment/<int:comment_id>/reject")
def admin_reject_comment(comment_id: int):
    if not _admin_require():
        return redirect(url_for("main.public_feed"))
    c = Comment.query.get_or_404(comment_id)
    c.moderation_status = "rejected"
    c.is_visible = False
    escalate_strike(c.user)
    db.session.commit()
    flash("Commento rifiutato.", "warning")
    return redirect(request.referrer or url_for("main.admin_moderation_html"))

@bp.get("/api")
def hello():
    return "Social del corso: Flask è attivo ✅"

@bp.post("/api/students")
def create_student_api():
    data = request.get_json(force=True)
    s = Student(
        nome=data.get("nome"),
        email=(data.get("email") or "").strip().lower() or None,
        corso=data.get("corso"),
        programmi=data.get("programmi"),
        immagine_profilo=data.get("immagine_profilo"),
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"id": s.id, "nome": s.nome}), 201

@bp.post("/api/posts")
def create_post_api():
    data = request.get_json(force=True)
    author_id = data["author_id"]
    user = Student.query.get_or_404(author_id)

    content = (data.get("content") or "").strip() or None
    image_url = data.get("image_url")
    video_url = data.get("video_url")

    if not any([content, image_url, video_url]):
        return jsonify({"error": "empty post"}), 400

    mod = assess(content or "")
    status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
    status = status_map[mod.action]
    is_visible = (status == "approved") and (not user.is_shadow_banned)

    p = Post(
        author_id=author_id,
        content=content,
        image_url=image_url,
        video_url=video_url,
        moderation_status=status,
        toxicity_score=mod.score,
        is_visible=is_visible,
    )
    db.session.add(p)

    if mod.action == "reject":
        escalate_strike(user)

    db.session.commit()
    return jsonify(p.to_dict()), 201

@bp.get("/api/posts")
def list_posts_api():
    posts = Post.query.order_by(Post.created_at.desc()).all()
    return jsonify([p.to_dict() for p in posts])

@bp.route("/api/posts/<int:post_id>", methods=["PUT", "PATCH"])
def update_post_api(post_id):
    data = request.get_json(force=True)
    post = Post.query.get_or_404(post_id)
    user_id = data.get("user_id")
    if user_id is not None and user_id != post.author_id:
        return jsonify({"error": "not allowed"}), 403

    content = (data.get("content", post.content) or "").strip() or None
    image_url = data.get("image_url", post.image_url)
    video_url = data.get("video_url", post.video_url)

    if not any([content, image_url, video_url]):
        return jsonify({"error": "empty post"}), 400

    mod = assess(content or "")
    status_map = {"approve": "approved", "pending": "pending", "reject": "rejected"}
    status = status_map[mod.action]
    author = Student.query.get(post.author_id)
    is_visible = (status == "approved") and (not (author and author.is_shadow_banned))

    post.content = content
    post.image_url = image_url
    post.video_url = video_url
    post.moderation_status = status
    post.toxicity_score = mod.score
    post.is_visible = is_visible

    if mod.action == "reject":
        escalate_strike(author)

    db.session.commit()
    return jsonify(post.to_dict())

@bp.delete("/api/posts/<int:post_id>")
def delete_post_api(post_id):
    post = Post.query.get_or_404(post_id)
    db.session.delete(post)
    db.session.commit()
    return jsonify({"deleted": True, "post_id": post_id})

@bp.post("/api/posts/<int:post_id>/like/toggle")
@limiter.limit("30 per 5 minutes")
def api_toggle_like(post_id: int):
    if not session.get("user_id"):
        return jsonify({"error": "not authenticated"}), 401
    user_id = session["user_id"]
    post = Post.query.get_or_404(post_id)

    existing = Like.query.filter_by(user_id=user_id, post_id=post_id).first()
    if existing:
        db.session.delete(existing)
        db.session.commit()
        return jsonify({"status": "unliked", "post_id": post_id, "user_id": user_id, "likes_count": len(post.likes)}), 200
    else:
        db.session.add(Like(user_id=user_id, post_id=post_id))
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({"error": "like already exists"}), 409
        return jsonify({"status": "liked", "post_id": post_id, "user_id": user_id, "likes_count": len(post.likes)}), 201

@bp.get("/api/posts/<int:post_id>/like")
def api_like_status(post_id: int):
    post = Post.query.get_or_404(post_id)
    uid = session.get("user_id")
    liked_by_me = False
    if uid:
        liked_by_me = Like.query.filter_by(user_id=uid, post_id=post_id).first() is not None
    return jsonify({"post_id": post_id, "likes_count": len(post.likes), "liked_by_me": liked_by_me})
