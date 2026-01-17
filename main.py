from flask import Flask, render_template, request, redirect, flash, session, url_for
from sqlalchemy import or_, and_, not_, literal, union, func, extract, exists, desc
from datetime import datetime, date
from dotenv import load_dotenv
from models import *
import os
import os
import google.generativeai as genai
from sqlalchemy import text, inspect
from flask import current_app

app = Flask(__name__)

load_dotenv()

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")

db.init_app(app)

ADMIN_EMAIL = "admin@ensa.ma"
ADMIN_PASSWORD = "admin123"


genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

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

        if email == ADMIN_EMAIL and password == ADMIN_PASSWORD:
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
    events = Evenement.query.all()
    sponsors = Sponsor.query.all()
    intervenants = Intervenant.query.all()

    pending_inscriptions = Inscription.query.filter_by(Statut='En attente').all()
    pending_participations = Participation.query.filter_by(Statut='En attente').all()

    stats = {
        'count_etudiants': len(etudiants),
        'count_clubs': len(clubs),
        'count_events': len(events),
        'count_sponsors': len(sponsors),
        'count_intervenants': len(intervenants),
        'total_budget': sum(s.Contribution for s in sponsors if s.Contribution)
    }

    evenements_a_venir = Evenement.query.filter(Evenement.DateDebut >= datetime.now()).order_by(Evenement.DateDebut).limit(5).all()
    dernieres_inscriptions = Inscription.query.filter_by(Statut='valide').order_by(db.func.random()).limit(5).all()
    activites_recentes = ActiviteEV.query.order_by(ActiviteEV.DateActiviteE.desc()).limit(5).all()
    
    return render_template('dashboard.html', 
                            title='Tableau de bord Admin',
                            stats=stats,
                            pending_inscriptions=pending_inscriptions, 
                            pending_participations=pending_participations,
                            evenements=evenements_a_venir,
                            inscriptions=dernieres_inscriptions,
                            activites=activites_recentes)


# 🚨🚨🚨🚨🚨
@app.route('/admin/recherche', methods=['GET', 'POST'])
def recherche_avancee():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    resultats = []
    
    terme = request.args.get('q', '') or request.form.get('terme', '')
    type_recherche = request.args.get('type', '') or request.form.get('type', 'etudiant')
    
    filtre_budget = request.form.get('budget_min')
    filtre_date = request.form.get('date_min')
    filtre_club = request.form.get('club_filter')
    filtre_exclure = request.form.get('exclude_active') 

    if request.method == 'POST' or terme:
    
        if type_recherche == 'etudiant':
            query = Etudiant.query
            
            if filtre_club:
                query = query.join(Inscription).join(Club).filter(Club.NomClub.ilike(f'%{filtre_club}%'))
            
            if filtre_exclure == 'sans_club':
                query = query.outerjoin(Inscription).filter(Inscription.CodeClub == None)

            if terme:
                query = query.filter(
                    or_(
                        Etudiant.Nom.ilike(f'%{terme}%'),
                        Etudiant.Prenom.ilike(f'%{terme}%'),
                        Etudiant.Filiere.ilike(f'%{terme}%')
                    )
                )
            resultats = query.all()

        elif type_recherche == 'club':
            query = Club.query
            
            if terme and "etudiant:" in terme:
                student_name = terme.split(":")[1].strip()
                query = query.join(Inscription).join(Etudiant).filter(
                    or_(Etudiant.Nom.ilike(f'%{student_name}%'), Etudiant.Prenom.ilike(f'%{student_name}%'))
                )
            elif terme:
                query = query.filter(Club.NomClub.ilike(f'%{terme}%'))
            
            resultats = query.all()

        elif type_recherche == 'evenement':
            query = Evenement.query
            
            if filtre_date:
                query = query.filter(Evenement.DateDebut >= datetime.strptime(filtre_date, '%Y-%m-%d'))

            if terme:
                query = query.filter(
                    or_(
                        Evenement.NomEvent.ilike(f'%{terme}%'),
                        Evenement.Theme.ilike(f'%{terme}%'),
                        Evenement.Filiere.ilike(f'%{terme}%')
                    )
                )
            resultats = query.all()

        elif type_recherche == 'sponsor':
            query = Sponsor.query
            
            if filtre_budget:
                query = query.filter(Sponsor.Contribution >= float(filtre_budget))
            
            if terme:
                query = query.filter(Sponsor.NomSponsor.ilike(f'%{terme}%'))
                
            resultats = query.all()

        elif type_recherche == 'intervenant':
            query = Intervenant.query
            
            if terme:
                query = query.filter(Intervenant.Specialite.ilike(f'%{terme}%'))
            
            resultats = query.all()
    
    return render_template('recherche.html',
                        title='Recherche Avancée',
                        resultats=resultats,
                        terme=terme,
                        type_recherche=type_recherche,
                        filtre_budget=filtre_budget,
                        filtre_date=filtre_date,
                        filtre_club=filtre_club)


# 🚨🚨🚨🚨🚨
def get_db_schema(db):
    """
    Dynamically extracts the schema from your SQLAlchemy models.
    This ensures Gemini knows exactly what columns exist (e.g., CodeEtudiant, not 'id').
    """
    schema_lines = ["SQLAlchemy Database Schema for SQLite/PostgreSQL:"]
    
    # Use SQLAlchemy inspector to get table details
    inspector = inspect(db.engine)
    
    for table_name in inspector.get_table_names():
        columns = inspector.get_columns(table_name)
        col_strings = [f"{col['name']} ({col['type']})" for col in columns]
        schema_lines.append(f"Table '{table_name}': " + ", ".join(col_strings))
        
        # Add Foreign Keys to help AI understand joins
        fks = inspector.get_foreign_keys(table_name)
        if fks:
            fk_strings = [f"FK: {fk['constrained_columns']} -> {fk['referred_table']}.{fk['referred_columns']}" for fk in fks]
            schema_lines.append("  " + " | ".join(fk_strings))

    # Explicitly mention Many-to-Many tables if they aren't obvious
    schema_lines.append("Note: 'sponsoriser' links Club <-> Sponsor.")
    schema_lines.append("Note: 'financer' links Event <-> Sponsor.")
    schema_lines.append("Note: 'animer' links Intervenant <-> ActiviteEV.")
    
    return "\n".join(schema_lines)

def ask_gemini_db(db, user_question):
    """
    Uses Gemini Flash to convert natural language to SQL and executes it.
    """
    
    # 1. Select the Model (Gemini 1.5 Flash or 2.0 Flash)
    # Note: Use 'gemini-1.5-flash' or 'gemini-2.0-flash-exp' depending on availability
    model = genai.GenerativeModel('gemini-2.5-flash-lite') 
    
    # 2. Build the Prompt
    schema_context = get_db_schema(db)
    
    prompt = f"""
    You are an expert SQL Data Analyst.
    
    CONTEXT (Database Schema):
    {schema_context}
    
    USER QUESTION:
    "{user_question}"
    
    INSTRUCTIONS:
    1. Generate a valid SQL query to answer the question.
    2. Use ONLY the table and column names provided in the schema.
    3. Return ONLY the raw SQL code. Do not wrap it in markdown (no ```sql).
    4. Do not include explanations.
    5. If the request is dangerous (DELETE, DROP, UPDATE), return "ERROR: UNSAFE".
    """

    try:
        # 3. Generate Content
        response = model.generate_content(prompt)
        generated_sql = response.text.strip()
        
        # Cleanup: Remove markdown if Gemini adds it despite instructions
        generated_sql = generated_sql.replace('```sql', '').replace('```', '').strip()
        
        print(f"DEBUG SQL: {generated_sql}") # Useful for debugging

        if "ERROR: UNSAFE" in generated_sql:
            return {"status": "error", "message": "Modification operations are not allowed."}

        # 4. Execute Query
        with db.engine.connect() as connection:
            result = connection.execute(text(generated_sql))
            headers = result.keys()
            rows = [dict(zip(headers, row)) for row in result.fetchall()]
            
            return {
                "status": "success",
                "question": user_question,
                "sql": generated_sql,
                "count": len(rows),
                "data": rows,
                "headers": list(headers)
            }

    except Exception as e:
        return {"status": "error", "message": str(e)}

from flask import request, jsonify

@app.route('/api/ask', methods=['POST'])
def handle_natural_language_request():
    data = request.json
    question = data.get('question')
    
    if not question:
        return jsonify({"error": "No question provided"}), 400
        
    # Call the Gemini function
    result = ask_gemini_db(db, question)
    
    if result['status'] == 'error':
        return jsonify(result), 500
        
    return jsonify(result)

@app.route('/admin/smart-search')
def view_smart_search():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    return render_template('ai_search.html')


@app.route('/admin/valider_inscription/<int:et_id>/<int:cl_id>')
def valider_inscription(et_id, cl_id):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))

    demande = Inscription.query.filter_by(CodeEtudiant=et_id, CodeClub=cl_id).first()
    if demande:
        demande.Statut = "valide"
        db.session.commit()
        flash("Inscription validée !", "success")

    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/refuser_inscription/<int:et_id>/<int:cl_id>')
def refuser_inscription(et_id, cl_id):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))

    demande = Inscription.query.filter_by(CodeEtudiant=et_id, CodeClub=cl_id).first()
    if demande:
        db.session.delete(demande)
        db.session.commit()
        flash("Inscription refusée (supprimée).", "warning")

    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/valider_participation/<int:et_id>/<int:evt_id>')
def valider_participation(et_id, evt_id):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))

    participation = Participation.query.filter_by(CodeEtudiant=et_id, CodeEvent=evt_id).first()
    if participation:
        participation.Statut = "valide"
        db.session.commit()
        flash("Participation validée !", "success")

    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/refuser_participation/<int:et_id>/<int:evt_id>')
def refuser_participation(et_id, evt_id):
    if session.get('user_type') != 'admin': return redirect(url_for('login'))

    participation = Participation.query.filter_by(CodeEtudiant=et_id, CodeEvent=evt_id).first()
    if participation:
        db.session.delete(participation)
        db.session.commit()
        flash("Participation refusée (supprimée).", "warning")

    return redirect(request.referrer or url_for('admin_dashboard'))


@app.route('/admin/etudiants')
def gestion_etudiants():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    etudiants = Etudiant.query.all()
    return render_template('listeE.html',
                            title='Gestion des étudiants',
                            etudiants=etudiants)


@app.route('/admin/etudiant/ajouter', methods=['GET', 'POST'])
def ajouter_etudiant():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            etudiant = Etudiant(
                Nom=request.form.get('nom'),
                Prenom=request.form.get('prenom'),
                Filiere=request.form.get('filiere'),
                DateNaissance=datetime.strptime(request.form.get('date_naissance'), '%Y-%m-%d'),
                Email=request.form.get('email'),
                MotDePasse=request.form.get('mot_de_passe'),
                Telephone=request.form.get('telephone')
            )
            
            db.session.add(etudiant)
            db.session.commit()
            flash('Étudiant ajouté avec succès!', 'success')
            return redirect(url_for('gestion_etudiants'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterE.html',
                            title='Ajouter un étudiant')


@app.route('/admin/etudiant/<int:id>')
def detail_etudiant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    etudiant = Etudiant.query.get_or_404(id)
    inscriptions = Inscription.query.filter_by(CodeEtudiant=id).all()
    participations = Participation.query.filter_by(CodeEtudiant=id).all()
    
    return render_template('detailE.html',
                            title=f'Étudiant: {etudiant.Prenom} {etudiant.Nom}',
                            etudiant=etudiant,
                            inscriptions=inscriptions,
                            participations=participations)


@app.route('/admin/etudiant/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_etudiant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    etudiant = Etudiant.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            etudiant.Nom = request.form.get('nom')
            etudiant.Prenom = request.form.get('prenom')
            etudiant.Filiere = request.form.get('filiere')
            etudiant.DateNaissance = datetime.strptime(request.form.get('date_naissance'), '%Y-%m-%d')
            etudiant.Email = request.form.get('email')
            etudiant.MotDePasse = request.form.get('mot_de_passe')
            etudiant.Telephone = request.form.get('telephone')
            
            db.session.commit()
            flash('Étudiant modifié avec succès!', 'success')
            return redirect(url_for('gestion_etudiants'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierE.html',
                            title=f'Modifier {etudiant.Prenom} {etudiant.Nom}',
                            etudiant=etudiant)


@app.route('/admin/etudiant/<int:id>/supprimer')
def supprimer_etudiant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    etudiant = Etudiant.query.get_or_404(id)
    
    try:
        Inscription.query.filter_by(CodeEtudiant=id).delete()
        Participation.query.filter_by(CodeEtudiant=id).delete()
        
        db.session.delete(etudiant)
        db.session.commit()
        flash('Étudiant supprimé avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_etudiants'))


@app.route('/admin/clubs')
def gestion_clubs():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    clubs = Club.query.all()
    return render_template('listeC.html',
                            title='Gestion des clubs',
                            clubs=clubs)


@app.route('/admin/club/ajouter', methods=['GET', 'POST'])
def ajouter_club():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            club = Club(
                NomClub=request.form.get('nom'),
                TypeClub=request.form.get('type'),
                DescriptionC=request.form.get('description')
            )
            
            db.session.add(club)
            db.session.commit()
            flash('Club ajouté avec succès!', 'success')
            return redirect(url_for('gestion_clubs'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterC.html',
                        title='Ajouter un club')


@app.route('/admin/club/<int:id>')
def detail_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    club = Club.query.get_or_404(id)
    inscriptions = Inscription.query.filter_by(CodeClub=id).all()
    activites = ActiviteC.query.filter_by(CodeClub=id).all()
    sponsors = club.sponsors
    
    return render_template('detailC.html',
                        title=f'Club: {club.NomClub}',
                        club=club,
                        inscriptions=inscriptions,
                        activites=activites,
                        sponsors=sponsors)


@app.route('/admin/club/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    club = Club.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            club.NomClub = request.form.get('nom')
            club.TypeClub = request.form.get('type')
            club.DateCreation = datetime.strptime(request.form.get('date_creation'), '%Y-%m-%d')
            club.DescriptionC = request.form.get('description')
            
            db.session.commit()
            flash('Club modifié avec succès!', 'success')
            return redirect(url_for('gestion_clubs'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierC.html',
                            title=f'Modifier {club.NomClub}',
                            club=club)


@app.route('/admin/club/<int:id>/supprimer')
def supprimer_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    club = Club.query.get_or_404(id)
    
    try:
        Inscription.query.filter_by(CodeClub=id).delete()
        ActiviteC.query.filter_by(CodeClub=id).delete()
        
        db.session.delete(club)
        db.session.commit()
        flash('Club supprimé avec succès!', 'success')

    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_clubs'))


@app.route('/admin/club/<int:club_id>/ajouter_membre', methods=['GET', 'POST'])
def ajouter_membre_club(club_id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    club = Club.query.get_or_404(club_id)
    etudiants = Etudiant.query.all()

    if request.method == 'POST':
        etudiant_id = request.form.get('etudiant_id')
        role = request.form.get('role') or 'Membre'
        statut = request.form.get('statut') or 'valide'

        if not etudiant_id:
            flash("Sélectionnez un étudiant.", "error")
            return redirect(request.url)

        existing = Inscription.query.filter_by(CodeEtudiant=etudiant_id, CodeClub=club_id).first()
        if existing:
            flash("L'étudiant est déjà membre de ce club.", "warning")
            return redirect(request.referrer or url_for('detail_club', id=club_id))

        try:
            inscription = Inscription(CodeEtudiant=etudiant_id, CodeClub=club_id,
                                    TypeMembre=role, Statut=statut, MessageAdmin=None)
            db.session.add(inscription)
            db.session.commit()
            flash("Membre ajouté au club avec succès.", "success")
            return redirect(url_for('detail_club', id=club_id))
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout du membre: {e}", "error")
            return redirect(request.referrer or url_for('detail_club', id=club_id))

    return render_template('ajouter_membre_club.html', club=club, etudiants=etudiants)


@app.route('/admin/club/<int:club_id>/supprimer_membre/<int:et_id>')
def supprimer_membre_club(club_id, et_id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    inscription = Inscription.query.filter_by(CodeClub=club_id, CodeEtudiant=et_id).first()
    if inscription:
        try:
            db.session.delete(inscription)
            db.session.commit()
            flash("Membre retiré du club.", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la suppression: {e}", "error")
    else:
        flash("Inscription introuvable.", "warning")

    return redirect(request.referrer or url_for('detail_club', id=club_id))


@app.route('/admin/activites_club')
def gestion_activites_club():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activites = ActiviteC.query.all()
    return render_template('listeAC.html',
                        title='Activités des Clubs',
                        activites=activites)


@app.route('/admin/activite_club/ajouter', methods=['GET', 'POST'])
def ajouter_activite_club():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    clubs_list = Club.query.all()

    if request.method == 'POST':
        try:
            club_id = request.form.get('club_id')
            if not club_id:
                flash("Une activité doit être liée à un club.", "error")
                return redirect(request.url)

            # Check if date is provided
            date_str = request.form.get('date')
            if not date_str:
                 flash("La date est obligatoire.", "error")
                 return redirect(request.url)

            activite = ActiviteC(
            IntituleC=request.form.get('intitule'),
            DateActiviteC=datetime.strptime(request.form.get('date'), '%Y-%m-%d'),
            Duree=request.form.get('duree'),
            Lieu=request.form.get('lieu'),
            CodeClub=request.form.get('club_id'),
            # NEW FIELDS
            Budget=float(request.form.get('budget') or 0),
            Rating=int(request.form.get('rating') or 0)
            )

            db.session.add(activite)
            db.session.commit()
            
            flash('Activité club ajoutée avec succès!', 'success')
            return redirect(url_for('gestion_activites_club'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterAC.html',
                           title='Ajouter une activité club',
                           clubs=clubs_list)


@app.route('/admin/activite_club/<int:id>')
def detail_activite_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteC.query.get_or_404(id)
    
    return render_template('detailAC.html',
                        title=f'Activité: {activite.IntituleC}',
                        activite=activite)


@app.route('/admin/activite_club/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_activite_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteC.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            # 1. Update Standard Fields
            activite.IntituleC = request.form.get('intitule')
            # Note: Your model has 'IntituleC', 'DateActiviteC', 'Duree', 'Lieu'. 
            # It does NOT have 'TypeActiviteC' or 'DescriptionC'.
            
            activite.DateActiviteC = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            activite.Duree = request.form.get('duree')
            activite.Lieu = request.form.get('lieu')

            # 2. Update New Fields (Budget & Rating)
            # Use 'or 0' to handle empty inputs gracefully
            activite.Budget = float(request.form.get('budget') or 0.0)
            activite.Rating = int(request.form.get('rating') or 0)

            db.session.commit()
            flash('Activité modifiée avec succès!', 'success')
            return redirect(url_for('gestion_activites_club'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierAC.html',
                           title=f'Modifier {activite.IntituleC}',
                           activite=activite)


@app.route('/admin/activite_club/<int:id>/supprimer')
def supprimer_activite_club(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteC.query.get_or_404(id)
    
    try:
        db.session.delete(activite)
        db.session.commit()
        flash('Activité supprimée avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_activites_club'))


@app.route('/admin/evenements')
def gestion_evenements():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    evenements = Evenement.query.all()
    return render_template('listeEV.html',
                            title='Gestion des événements',
                            evenements=evenements)


@app.route('/admin/evenement/ajouter', methods=['GET', 'POST'])
def ajouter_evenement():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            evenement = Evenement(
                NomEvent=request.form.get('nom'),
                Filiere=request.form.get('filiere'),
                Theme=request.form.get('theme'),
                DateDebut=datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d'),
                DateFin=datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d'),
                LieuE=request.form.get('lieu'),
                DescriptionE=request.form.get('description')
            )
            
            db.session.add(evenement)
            db.session.commit()
            flash('Événement ajouté avec succès!', 'success')
            return redirect(url_for('gestion_evenements'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterEV.html',
                            title='Ajouter un événement')


@app.route('/admin/evenement/<int:id>')
def detail_evenement(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    evenement = Evenement.query.get_or_404(id)
    participants = Participation.query.filter_by(CodeEvent=id).all()
    activites = ActiviteEV.query.filter_by(CodeEvent=id).all()
    sponsors = evenement.sponsors
    
    return render_template('detailEV.html',
                        title=f'Événement: {evenement.NomEvent}',
                        evenement=evenement,
                        participants=participants,
                        activites=activites,
                        sponsors=sponsors)


@app.route('/admin/evenement/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_evenement(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    evenement = Evenement.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            evenement.NomEvent = request.form.get('nom')
            evenement.Filiere = request.form.get('filiere')
            evenement.Theme = request.form.get('theme')
            evenement.DateDebut = datetime.strptime(request.form.get('date_debut'), '%Y-%m-%d')
            evenement.DateFin = datetime.strptime(request.form.get('date_fin'), '%Y-%m-%d')
            evenement.LieuE = request.form.get('lieu')
            evenement.DescriptionE = request.form.get('description')
            
            db.session.commit()
            flash('Événement modifié avec succès!', 'success')
            return redirect(url_for('gestion_evenements'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierEV.html',
                        title=f'Modifier {evenement.NomEvent}',
                        evenement=evenement)


@app.route('/admin/evenement/<int:id>/supprimer')
def supprimer_evenement(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    evenement = Evenement.query.get_or_404(id)
    
    try:
        Participation.query.filter_by(CodeEvent=id).delete()
        ActiviteEV.query.filter_by(CodeEvent=id).delete()
        
        db.session.delete(evenement)
        db.session.commit()
        flash('Événement supprimé avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_evenements'))


@app.route('/admin/evenement/<int:event_id>/ajouter_participant', methods=['GET', 'POST'])
def ajouter_participant_event(event_id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    evenement = Evenement.query.get_or_404(event_id)
    etudiants = Etudiant.query.all()

    if request.method == 'POST':
        etudiant_id = request.form.get('etudiant_id')
        role = request.form.get('role') or 'Participant'
        statut = request.form.get('statut') or 'valide'

        if not etudiant_id:
            flash("Sélectionnez un étudiant.", "error")
            return redirect(request.url)

        existing = Participation.query.filter_by(CodeEtudiant=etudiant_id, CodeEvent=event_id).first()
        if existing:
            flash("L'étudiant participe déjà à cet événement.", "warning")
            return redirect(request.referrer or url_for('detail_evenement', id=event_id))

        try:
            participation = Participation(CodeEtudiant=etudiant_id, CodeEvent=event_id,
                                        TypeParticipant=role, Statut=statut)
            db.session.add(participation)
            db.session.commit()
            flash("Participant ajouté à l'événement avec succès.", "success")
            return redirect(url_for('detail_evenement', id=event_id))
        
        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de l'ajout du participant: {e}", "error")
            return redirect(request.referrer or url_for('detail_evenement', id=event_id))

    return render_template('ajouter_participant_event.html', evenement=evenement, etudiants=etudiants)


@app.route('/admin/evenement/<int:event_id>/supprimer_participant/<int:et_id>')
def supprimer_participant_event(event_id, et_id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    participation = Participation.query.filter_by(CodeEvent=event_id, CodeEtudiant=et_id).first()
    if participation:
        try:
            db.session.delete(participation)
            db.session.commit()
            flash("Participant retiré de l'événement.", "success")

        except Exception as e:
            db.session.rollback()
            flash(f"Erreur lors de la suppression: {e}", "error")

    else:
        flash("Participation introuvable.", "warning")

    return redirect(request.referrer or url_for('detail_evenement', id=event_id))


@app.route('/admin/activites_event')
def gestion_activites_event():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activites = ActiviteEV.query.all()
    return render_template('listeAE.html',
                        title='Activités des Événements',
                        activites=activites)


@app.route('/admin/activite_event/ajouter', methods=['GET', 'POST'])
def ajouter_activite_event():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    events_list = Evenement.query.all()
    intervenants_list = Intervenant.query.all()

    if request.method == 'POST':
        try:

            event_id = request.form.get('event_id')
            if not event_id:
                flash("Une activité doit être liée à un événement.", "error")
                return redirect(request.url)

            activite = ActiviteEV(
                IntituleE=request.form.get('intitule'),
                TypeActiviteE=request.form.get('type'),
                DateActiviteE=datetime.strptime(request.form.get('date'), '%Y-%m-%d'),
                Duree=request.form.get('duree'),
                CodeEvent=event_id
            )

            intervenant_id = request.form.get('intervenant_id')
            if intervenant_id:
                intervenant = Intervenant.query.get(intervenant_id)
                if intervenant:
                    activite.intervenants.append(intervenant)

            db.session.add(activite)
            db.session.commit()
            
            flash('Activité événement ajoutée avec succès!', 'success')
            return redirect(url_for('gestion_activites_event'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterAE.html',
                            title='Ajouter une activité événement',
                            evenements=events_list,
                            intervenants=intervenants_list)


@app.route('/admin/activite_event/<int:id>')
def detail_activite_event(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteEV.query.get_or_404(id)
    intervenants = activite.intervenants
    
    return render_template('detailAE.html',
                        title=f'Activité: {activite.IntituleE}',
                        activite=activite,
                        intervenants=intervenants)


@app.route('/admin/activite_event/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_activite_event(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteEV.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            activite.IntituleE = request.form.get('intitule')
            activite.TypeActiviteE = request.form.get('type')
            activite.DateActiviteE = datetime.strptime(request.form.get('date'), '%Y-%m-%d')
            activite.Duree = request.form.get('duree')
            
            db.session.commit()
            flash('Activité modifiée avec succès!', 'success')
            return redirect(url_for('gestion_activites_event'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierAE.html',
                        title=f'Modifier {activite.IntituleE}',
                        activite=activite)


@app.route('/admin/activite_event/<int:id>/supprimer')
def supprimer_activite_event(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    activite = ActiviteEV.query.get_or_404(id)
    
    try:
        db.session.delete(activite)
        db.session.commit()
        flash('Activité supprimée avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_activites_event'))


@app.route('/admin/sponsors')
def gestion_sponsors():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    sponsors = Sponsor.query.all()
    return render_template('listeS.html',
                        title='Gestion des sponsors',
                        sponsors=sponsors)


@app.route('/admin/sponsor/ajouter', methods=['GET', 'POST'])
def ajouter_sponsor():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    clubs_list = Club.query.all()
    events_list = Evenement.query.all()

    if request.method == 'POST':
        try:
            sponsor = Sponsor(
                NomSponsor=request.form.get('nom'),
                TypeSponsor=request.form.get('type'),
                Contribution=float(request.form.get('contribution') or 0)
            )
            
            club_id = request.form.get('club_id')
            if club_id:
                club = Club.query.get(club_id)
                if club:
                    sponsor.clubs.append(club)
            
            event_id = request.form.get('event_id')
            if event_id:
                event = Evenement.query.get(event_id)
                if event:
                    sponsor.evenements.append(event)
            
            db.session.add(sponsor)
            db.session.commit()
            
            flash('Sponsor ajouté et lié avec succès!', 'success')
            return redirect(url_for('gestion_sponsors'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterS.html',
                            title='Ajouter un sponsor',
                            clubs=clubs_list, 
                            evenements=events_list) 


@app.route('/admin/sponsor/<int:id>')
def detail_sponsor(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    sponsor = Sponsor.query.get_or_404(id)
    clubs = sponsor.clubs
    evenements = sponsor.evenements
    
    return render_template('detailS.html',
                        title=f'Sponsor: {sponsor.NomSponsor}',
                        sponsor=sponsor,
                        clubs=clubs,
                        evenements=evenements)


@app.route('/admin/sponsor/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_sponsor(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    sponsor = Sponsor.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            sponsor.NomSponsor = request.form.get('nom')
            sponsor.TypeSponsor = request.form.get('type')
            sponsor.Contribution = float(request.form.get('contribution') or 0)
            
            db.session.commit()
            flash('Sponsor modifié avec succès!', 'success')
            return redirect(url_for('gestion_sponsors'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierS.html',
                        title=f'Modifier {sponsor.NomSponsor}',
                        sponsor=sponsor)


@app.route('/admin/sponsor/<int:id>/supprimer')
def supprimer_sponsor(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    sponsor = Sponsor.query.get_or_404(id)
    
    try:
        db.session.delete(sponsor)
        db.session.commit()
        flash('Sponsor supprimé avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_sponsors'))


@app.route('/admin/intervenants')
def gestion_intervenants():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    intervenants = Intervenant.query.all()
    return render_template('listeIN.html',
                        title='Gestion des intervenants',
                        intervenants=intervenants)


@app.route('/admin/intervenant/ajouter', methods=['GET', 'POST'])
def ajouter_intervenant():
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))

    activites_event_list = ActiviteEV.query.join(Evenement).order_by(Evenement.DateDebut.desc()).all()

    if request.method == 'POST':
        try:
            intervenant = Intervenant(
                NomIN=request.form.get('nom'),
                PrenomIN=request.form.get('prenom'),
                Specialite=request.form.get('specialite'),
                EmailIN=request.form.get('email'),
                TelephoneIN=request.form.get('telephone')
            )
            
            selected_activities = request.form.getlist('activites')
            
            for act_id in selected_activities:
                activite = ActiviteEV.query.get(act_id)
                if activite:
                    intervenant.activites.append(activite) 
            
            db.session.add(intervenant)
            db.session.commit()
            
            flash('Intervenant ajouté et affecté aux activités avec succès!', 'success')
            return redirect(url_for('gestion_intervenants'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('ajouterIN.html',
                        title='Ajouter un intervenant',
                        activites_list=activites_event_list) 


@app.route('/admin/intervenant/<int:id>')
def detail_intervenant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    intervenant = Intervenant.query.get_or_404(id)
    activites = intervenant.activites
    
    return render_template('detailIN.html',
                        title=f'Intervenant: {intervenant.PrenomIN} {intervenant.NomIN}',
                        intervenant=intervenant,
                        activites=activites)


@app.route('/admin/intervenant/<int:id>/modifier', methods=['GET', 'POST'])
def modifier_intervenant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    intervenant = Intervenant.query.get_or_404(id)
    
    if request.method == 'POST':
        try:
            intervenant.NomIN = request.form.get('nom')
            intervenant.PrenomIN = request.form.get('prenom')
            intervenant.Specialite = request.form.get('specialite')
            intervenant.EmailIN = request.form.get('email')
            intervenant.TelephoneIN = request.form.get('telephone')
            
            db.session.commit()
            flash('Intervenant modifié avec succès!', 'success')
            return redirect(url_for('gestion_intervenants'))
        
        except Exception as e:
            db.session.rollback()
            flash(f'Erreur: {str(e)}', 'error')
    
    return render_template('modifierIN.html',
                        title=f'Modifier {intervenant.PrenomIN} {intervenant.NomIN}',
                        intervenant=intervenant)


@app.route('/admin/intervenant/<int:id>/supprimer')
def supprimer_intervenant(id):
    if session.get('user_type') != 'admin':
        return redirect(url_for('login'))
    
    intervenant = Intervenant.query.get_or_404(id)
    
    try:
        db.session.delete(intervenant)
        db.session.commit()
        flash('Intervenant supprimé avec succès!', 'success')
    
    except Exception as e:
        db.session.rollback()
        flash(f'Erreur: {str(e)}', 'error')
    
    return redirect(url_for('gestion_intervenants'))


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))




if __name__ == "__main__":
    # Execute inside the application context
    with app.app_context():
        # 1. Add Budget Column
        try:
            with db.engine.connect() as connection:
               connection.execute(text("ALTER TABLE activite_c ADD COLUMN Budget FLOAT DEFAULT 0"))
               connection.commit()
            print("✅ Colonne 'Budget' ajoutée avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur ajout Budget (existe peut-être déjà): {e}")

        # 2. Add Rating Column
        try:
            with db.engine.connect() as connection:
                connection.execute(text("ALTER TABLE activite_c ADD COLUMN Rating INTEGER DEFAULT 0"))
                connection.commit()
            print("✅ Colonne 'Rating' ajoutée avec succès.")
        except Exception as e:
            print(f"⚠️ Erreur ajout Rating (existe peut-être déjà): {e}")
    app.run(debug=True, port=9000)




