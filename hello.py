from flask import Flask, render_template, request, redirect, flash, session, url_for
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
from models import *
import os
from datetime import datetime, date

app = Flask(__name__)

load_dotenv()

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

db.init_app(app)

ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = generate_password_hash(os.getenv("ADMIN_PASSWORD"))

@app.route('/')
def homepage():
    return render_template("homepage.html")

@app.route('/clubs')
def clubs():
    return render_template("clubs.html")

@app.route('/login', methods=['POST', 'GET'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email == ADMIN_EMAIL and check_password_hash(ADMIN_PASSWORD, password):
            session['user_type'] = 'admin'
            return redirect(url_for('admin_dashboard'))

        etudiant = Etudiant.query.filter_by(Email=email, MotDePasse=password).first()
        if etudiant:
            session['user_id'] = etudiant.CodeEtudiant
            session['user_name'] = etudiant.Nom
            session['user_type'] = 'etudiant'
            return redirect(url_for('member_dashboard'))
        else:
            flash("Email ou mot de passe incorrect.", "error")

    return render_template("login.html")

@app.route('/Member', methods=['GET', 'POST'])
def member_dashboard():
    if session.get('user_type') != 'etudiant':
        return redirect(url_for('login'))

    etudiant = Etudiant.query.filter_by(CodeEtudiant=session['user_id']).first()

    ids_clubs_inscrits = [i.CodeClub for i in etudiant.inscriptions]
    clubs_disponibles = Club.query.filter(Club.CodeClub.not_in(ids_clubs_inscrits)).all()

    ids_events_inscrits = [p.CodeEvent for p in etudiant.participations]
    events_disponibles = Evenement.query.filter(Evenement.CodeEvent.not_in(ids_events_inscrits)).all()

    return render_template('member.html', etudiant=etudiant, 
                            clubs_disponibles=clubs_disponibles, 
                            events_disponibles=events_disponibles)

@app.route('/demander_inscription/<int:etudiant_id>/<int:club_id>')
def demander_inscription(etudiant_id, club_id):
    nouvelle = Inscription(CodeEtudiant=etudiant_id, CodeClub=club_id, Statut="En attente")

    db.session.add(nouvelle)
    db.session.commit()

    return render_template('success.html', etudiant_id=etudiant_id, message="Demande de club envoyée !")

@app.route('/demander_participation/<int:etudiant_id>/<int:event_id>')
def demander_participation(etudiant_id, event_id):
    nouvelle = Participation(CodeEtudiant=etudiant_id, CodeEvent=event_id, Statut="En attente")

    db.session.add(nouvelle)
    db.session.commit()

    return render_template('success.html', etudiant_id=etudiant_id, message="Votre demande de participation à l'événement a été transmise !")

@app.route('/admin')
def admin_dashboard():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    etudiants = Etudiant.query.all()
    clubs = Club.query.all()
    events = Evenement.query.order_by(Evenement.DateDebut.desc()).all()
    sponsors = Sponsor.query.all()
    intervenants = Intervenant.query.all()

    stats = {
        'count_etudiants': len(etudiants),
        'count_clubs': len(clubs),
        'count_events': len(events),
        'count_sponsors': len(sponsors),
        'total_budget': sum(s.Contribution for s in sponsors if s.Contribution) 
    }

    return render_template("admin.html", 
                            etudiants=etudiants,
                            clubs=clubs,
                            events=events,
                            sponsors=sponsors,
                            intervenants=intervenants,
                            stats=stats)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == "__main__":
    with app.app_context():
        db.drop_all()
        db.create_all()

        # Students
        s1 = Etudiant(Nom='Doe', Prenom='John', Filiere='Computer Science',
                        DateNaissance=date(2000, 1, 1), Email='john.doe@example.com',
                        password='87654321', Telephone='+111111111')
        s2 = Etudiant(Nom='Nguyen', Prenom='Linh', Filiere='Information Systems',
                        DateNaissance=date(2001, 6, 15), Email='linh.nguyen@example.com',
                        password='12345678', Telephone='+222222222')

        # Clubs
        c1 = Club(NomClub='Robotics Club', TypeClub='Technology',
                    DateCreation=date(2020,5,1), DescriptionC='Robotics & automation')
        c2 = Club(NomClub='Photography Club', TypeClub='Arts',
                    DateCreation=date(2019,9,10), DescriptionC='Photos and editing')

        # Sponsors
        sp1 = Sponsor(NomSponsor='Acme Corp', TypeSponsor='Corporate', Contribution=5000.0)
        sp2 = Sponsor(NomSponsor='Local Books', TypeSponsor='Local Business', Contribution=800.0)

        # Link sponsors <> clubs
        c1.sponsors.append(sp1)
        c2.sponsors.append(sp2)

        # Club activities
        ac1 = ActiviteC(IntituleC='Intro to ROS', DateActiviteC=date(2024,11,10),
                        Duree='3h', Lieu='Lab 3', club=c1)
        ac2 = ActiviteC(IntituleC='Street Photography Walk', DateActiviteC=date(2024,12,1),
                        Duree='2h', Lieu='Campus', club=c2)

        # Events
        ev1 = Evenement(NomEvent='Tech Week 2025', Filiere='All', Theme='Innovation',
                        DateDebut=date(2025,3,10), DateFin=date(2025,3,12),
                        LieuE='Main Hall', DescriptionE='A week of tech talks and workshops')
        ev2 = Evenement(NomEvent='Creative Fest 2025', Filiere='All', Theme='Creativity',
                        DateDebut=date(2025,4,5), DateFin=date(2025,4,6),
                        LieuE='Auditorium', DescriptionE='Art & photo exhibitions')

        # Event sponsors (many-to-many)
        ev1.sponsors.append(sp1)
        ev2.sponsors.append(sp2)

        # Event activities and intervenants
        iev1 = Intervenant(NomIN='Smith', PrenomIN='Alice', Specialite='AI',
                            EmailIN='alice.smith@speaker.com', TelephoneIN='+333333333')
        ev_act1 = ActiviteEV(IntituleE='Keynote: Future of AI', TypeActiviteE='Talk',
                            DateActiviteE=datetime(2025,3,10,10,0), Duree='1h', evenement=ev1)
        ev_act1.intervenants.append(iev1)

        iev2 = Intervenant(NomIN='Brown', PrenomIN='Carlos', Specialite='Photography',
                            EmailIN='carlos.b@photomail.com', TelephoneIN='+444444444')
        ev_act2 = ActiviteEV(IntituleE='Street Photo Workshop', TypeActiviteE='Workshop',
                                DateActiviteE=datetime(2025,4,5,14,0), Duree='2h', evenement=ev2)
        ev_act2.intervenants.append(iev2)

        # Inscriptions (student <> club)
        ins1 = Inscription(club=c1, etudiant=s1, TypeMembre='Membre', Statut='valide', MessageAdmin=None)
        ins2 = Inscription(club=c2, etudiant=s2, TypeMembre='President', Statut='valide', MessageAdmin=None)

        # Participations (student <> event)
        p1 = Participation(etudiant=s1, evenement=ev1, TypeParticipant='Participant', Statut='valide')
        p2 = Participation(etudiant=s2, evenement=ev2, TypeParticipant='Volunteer', Statut='En attente')

        # Add all objects and commit
        db.session.add_all([s1, s2, c1, c2, sp1, sp2, ac1, ac2, ev1, ev2,
                            iev1, iev2, ev_act1, ev_act2, ins1, ins2, p1, p2])
        db.session.commit()

        # Print summary
        print("Seed complete: ", {
            "students": 2, "clubs": 2, "sponsors": 2, "club_activities": 2,
            "events": 2, "event_activities": 2, "intervenants": 2,
            "inscriptions": 2, "participations": 2
        })
    app.run(debug=True, port=9000)


