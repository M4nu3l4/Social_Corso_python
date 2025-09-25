# 📚 Social del Corso

Applicazione web sviluppata con **Flask** che consente agli studenti di condividere post, immagini, video, commentare e mettere like.  
Il progetto è stato realizzato come esercitazione didattica.

---

## 🚀 Funzionalità
- Registrazione e login utenti (studenti).
- Creazione di post con testo, immagini o video.
- Like e commenti ai post.
- Gestione profilo studente con foto.
- Bacheca pubblica con tutti i post.
- Moderazione (mute temporaneo utenti).
- Eliminazione automatica di post, commenti e like quando un utente viene rimosso.

---

 🛠️ Tecnologie
- [Flask](https://flask.palletsprojects.com/)
- [Flask-SQLAlchemy](https://flask-sqlalchemy.palletsprojects.com/)
- [Flask-Login](https://flask-login.readthedocs.io/)
- [Bootstrap 5](https://getbootstrap.com/)
- SQLite (database di default)


 📂 Struttura del progetto
```text

Social_Corso_python
├── ProgettoCorsoPythonBase/
│ ├── app/
│ │ ├── init.py
│ │ ├── models.py
│ │ ├── main.py
│ │ ├── templates/
│ │ │ ├── base.html
│ │ │ ├── bacheca.html
│ │ │ ├── login.html
│ │ │ └── register.html
│ │ └── static/
│ │ └── uploads/
│ ├── instance/
│ ├── migrations/
│ ├── config.py
│ ├── requirements.txt
│ └── wsgi.py
└── README.md




⚙️ Installazione

1. Clona la repository
   
   git clone https://github.com/tuo-username/Social_Corso_python.git
   cd Social_Corso_python/ProgettoCorsoPythonBase
Crea ed attiva l’ambiente virtuale

python -m venv venv
source venv/bin/activate     # Linux/Mac
venv\Scripts\activate        # Windows
Installa le dipendenze


pip install -r requirements.txt
Inizializza il database


flask shell
>>> from app import db
>>> db.create_all()
>>> exit()
Avvia il server


flask run
📝 To Do / Idee Future
Notifiche in tempo reale.

Chat privata tra studenti.

Pannello admin per gestione utenti.

👩‍💻 Autore
Progetto realizzato da Manuela come esercitazione di sviluppo web full-stack.


