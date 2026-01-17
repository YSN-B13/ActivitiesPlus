from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase
from datetime import datetime

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)

sponsoriser_association = db.Table('sponsoriser',
    db.Column('CodeClub', db.Integer, db.ForeignKey('club.CodeClub'), primary_key=True),
    db.Column('CodeSponsor', db.Integer, db.ForeignKey('sponsor.CodeSponsor'), primary_key=True)
)

financer_association = db.Table('financer',
    db.Column('CodeSponsor', db.Integer, db.ForeignKey('sponsor.CodeSponsor'), primary_key=True),
    db.Column('CodeEvent', db.Integer, db.ForeignKey('evenement.CodeEvent'), primary_key=True)
)

animer_association = db.Table('animer',
    db.Column('CodeIntervenant', db.Integer, db.ForeignKey('intervenant.CodeIntervenant'), primary_key=True),
    db.Column('CodeActiviteE', db.Integer, db.ForeignKey('activite_ev.CodeActiviteE'), primary_key=True)
)

class Etudiant(db.Model):
    __tablename__ = 'etudiant'
    CodeEtudiant = db.Column(db.Integer, primary_key=True)
    Nom = db.Column(db.String(120), nullable=False)
    Prenom = db.Column(db.String(120), nullable=False)
    Filiere = db.Column(db.String(100), nullable=False)
    DateNaissance = db.Column(db.Date)
    Email = db.Column(db.String(120), unique=True, nullable=False)
    MotDePasse = db.Column(db.String(255), nullable=False)
    Telephone = db.Column(db.String(120), nullable=False)

    inscriptions = db.relationship("Inscription", back_populates="etudiant")
    participations = db.relationship("Participation", back_populates="etudiant")

class Club(db.Model):
    __tablename__ = 'club'
    CodeClub = db.Column(db.Integer, primary_key=True)
    NomClub = db.Column(db.String(120), nullable=False)
    TypeClub = db.Column(db.String(120))
    DateCreation = db.Column(db.Date, default=datetime.utcnow().date())
    DescriptionC = db.Column(db.Text)

    inscriptions = db.relationship("Inscription", back_populates="club")
    activites = db.relationship("ActiviteC", back_populates="club")
    sponsors = db.relationship("Sponsor", secondary=sponsoriser_association, back_populates="clubs") # List

class Inscription(db.Model):
    __tablename__ = 'inscrir'
    CodeClub = db.Column(db.Integer, db.ForeignKey('club.CodeClub'), primary_key=True)
    CodeEtudiant = db.Column(db.Integer, db.ForeignKey('etudiant.CodeEtudiant'), primary_key=True)
    TypeMembre = db.Column(db.String(50), default="Membre")
    Statut = db.Column(db.String(20), default="En attente")
    MessageAdmin = db.Column(db.Text, nullable=True)

    club = db.relationship("Club", back_populates="inscriptions")
    etudiant = db.relationship("Etudiant", back_populates="inscriptions")

class ActiviteC(db.Model):
    __tablename__ = 'activite_c'
    CodeActiviteC = db.Column(db.Integer, primary_key=True)
    IntituleC = db.Column(db.String(100))
    DateActiviteC = db.Column(db.Date, unique=True)
    Duree = db.Column(db.String(50))
    Lieu = db.Column(db.String(100))
    Budget = db.Column(db.Float, default=0.0)
    Rating = db.Column(db.Integer, default=0)

    CodeClub = db.Column(db.Integer, db.ForeignKey('club.CodeClub'), nullable=False)
    club = db.relationship("Club", back_populates="activites")

class Evenement(db.Model):
    __tablename__ = 'evenement'
    CodeEvent = db.Column(db.Integer, primary_key=True)
    NomEvent = db.Column(db.String(100), nullable=False)
    Filiere = db.Column(db.String(100))
    Theme = db.Column(db.String(100))
    DateDebut = db.Column(db.Date, unique=True)
    DateFin = db.Column(db.Date, unique=True)
    LieuE = db.Column(db.String(100))
    DescriptionE = db.Column(db.Text)

    participants = db.relationship("Participation", back_populates="evenement")
    activites_ev = db.relationship("ActiviteEV", back_populates="evenement")
    sponsors = db.relationship("Sponsor", secondary=financer_association, back_populates="evenements") # List

class Participation(db.Model):
    __tablename__ = 'participer'
    CodeEtudiant = db.Column(db.Integer, db.ForeignKey('etudiant.CodeEtudiant'), primary_key=True)
    CodeEvent = db.Column(db.Integer, db.ForeignKey('evenement.CodeEvent'), primary_key=True)
    TypeParticipant = db.Column(db.String(50), default="Participant")
    Statut = db.Column(db.String(20), default="En attente")

    etudiant = db.relationship("Etudiant", back_populates="participations")
    evenement = db.relationship("Evenement", back_populates="participants")

class ActiviteEV(db.Model):
    __tablename__ = 'activite_ev'
    CodeActiviteE = db.Column(db.Integer, primary_key=True)
    IntituleE = db.Column(db.String(100))
    TypeActiviteE = db.Column(db.String(50))
    DateActiviteE = db.Column(db.DateTime, unique=True)
    Duree = db.Column(db.String(50))

    CodeEvent = db.Column(db.Integer, db.ForeignKey('evenement.CodeEvent'), nullable=False)
    evenement = db.relationship("Evenement", back_populates="activites_ev")
    intervenants = db.relationship("Intervenant", secondary=animer_association, back_populates="activites") # List

class Sponsor(db.Model):
    __tablename__ = 'sponsor'
    CodeSponsor = db.Column(db.Integer, primary_key=True)
    NomSponsor = db.Column(db.String(100), nullable=False)
    TypeSponsor = db.Column(db.String(50))
    Contribution = db.Column(db.Float)

    clubs = db.relationship("Club", secondary=sponsoriser_association, back_populates="sponsors") # List
    evenements = db.relationship("Evenement", secondary=financer_association, back_populates="sponsors") # List

class Intervenant(db.Model):
    __tablename__ = 'intervenant'
    CodeIntervenant = db.Column(db.Integer, primary_key=True)
    NomIN = db.Column(db.String(80))
    PrenomIN = db.Column(db.String(80))
    Specialite = db.Column(db.String(100))
    EmailIN = db.Column(db.String(120))
    TelephoneIN = db.Column(db.String(20))

    activites = db.relationship("ActiviteEV", secondary=animer_association, back_populates="intervenants") # List
