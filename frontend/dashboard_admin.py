# frontend/dashboard_admin.py - VERSION COMPLÈTE AVEC DÉCONNEXION
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import sys
import os
import time

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

try:
    from backend.database import (
        get_connection, fetch_formations, fetch_salles, fetch_professeurs,
        fetch_etudiants, fetch_all_users, fetch_examens,
        create_session, fetch_sessions, fetch_examens_by_session,
        fetch_examens_by_session_grouped, create_user,
        verify_password_strength
    )
    from backend.algorithm_simple import SimplePlanningGenerator, create_session_and_generate_exams, planify_session_exams, regenerate_session_completely_interface
    ALGO_AVAILABLE = True
except ImportError as e:
    ALGO_AVAILABLE = False
    st.warning(f"Modules non disponibles: {e}")

def show_dashboard():
    """Tableau de bord admin complet avec toutes les fonctionnalités"""
    st.title("👨‍💻 Tableau de Bord Administrateur - EDT Exam")
    
    # Menu en boutons radio vertical
    st.sidebar.markdown("### 📌 Navigation")
    
    # Options du menu avec icônes
    menu_options = [
        ("📊", "Vue d'ensemble"),
        ("➕", "Créer Session"),
        ("📋", "Sessions Existantes"),
        ("🏫", "Gestion des Salles"),
        ("👨‍🏫", "Gestion des Professeurs"),
        ("👨‍🎓", "Gestion des Étudiants"),
        ("📚", "Gestion des Modules/Formations"),
        ("👥", "Gestion des Groupes"),
        ("🏢", "Gestion des Départements"),
       
    ]
    
    # Créer des boutons radio avec icônes et labels
    selected = st.sidebar.radio(
        "Choisir une section :",
        [option[1] for option in menu_options],
        index=0,
        label_visibility="collapsed"
    )
    
    # AJOUTER ICI : Bouton de déconnexion dans la barre latérale
    st.sidebar.markdown("---")  # Ligne de séparation
    if st.sidebar.button("🚪 Déconnexion", use_container_width=True, type="secondary"):
        # Nettoyer la session
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()
    
    
    # Router vers la fonction appropriée
    if selected == "Vue d'ensemble":
        show_overview()
    elif selected == "Créer Session":
        show_new_session()
    elif selected == "Sessions Existantes":
        show_existing_sessions()
    elif selected == "Gestion des Salles":
        manage_salles()
    elif selected == "Gestion des Professeurs":
        manage_professeurs()
    elif selected == "Gestion des Étudiants":
        manage_etudiants()
    elif selected == "Gestion des Modules/Formations":
        manage_modules_formations()
    elif selected == "Gestion des Groupes":
        manage_groupes()
    elif selected == "Gestion des Départements":
        manage_departements()
    

def show_overview():
    
    st.header("📊 Vue d'ensemble du système")
    conn = get_connection()
    if conn:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT COUNT(*) as nb_refused 
            FROM examens 
            WHERE statut = 'REFUSE'
        """)
        result = cursor.fetchone()
        conn.close()
        
        if result and result['nb_refused'] > 0:
            st.error(f"🚨 {result['nb_refused']} examen(s) refusé(s) par le chef de département")
            
           
            st.divider()
    try:
        # Récupérer les données
        sessions = fetch_sessions()
        salles = fetch_salles()
        professeurs = fetch_professeurs()
        etudiants = fetch_etudiants()
        examens = fetch_examens()
        formations = fetch_formations()
        
        # Afficher les métriques dans 3 colonnes
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("🗓️ Sessions d'examens", len(sessions))
            st.metric("🏫 Salles disponibles", len(salles))
            st.metric("📚 Formations", len(formations))
        
        with col2:
            st.metric("👨‍🏫 Professeurs", len(professeurs))
            st.metric("👨‍🎓 Étudiants", len(etudiants))
            st.metric("📝 Examens programmés", len([e for e in examens if e['statut'] == 'CONFIRME']))
        
        with col3:
            st.metric("⏳ Examens en attente", len([e for e in examens if e['statut'] == 'EN_ATTENTE']))
            st.metric("🎓 Amphithéâtres", len([s for s in salles if s['type'] == 'AMPHI']))
            st.metric("🪑 Salles de cours", len([s for s in salles if s['type'] == 'SALLE']))
        
        st.divider()
        
        # Dernières sessions
        
    except Exception as e:
        st.error(f"❌ Erreur lors du chargement des données: {e}")

def show_new_session():
    """Créer une nouvelle session"""
    st.header("➕ Créer une nouvelle session d'examens")
    
    # Initialiser session_state
    if 'creation_results' not in st.session_state:
        st.session_state.creation_results = None
    
    # Formulaire de création
    with st.form("new_session_form"):
        st.subheader("📋 Informations de la session")
        
        col1, col2 = st.columns(2)
        
        with col1:
            session_name = st.text_input("Nom de la session *", placeholder="Ex: Session Automne 2024")
        
        with col2:
            default_start = datetime.now().date() + timedelta(days=7)
            start_date = st.date_input("Date de début *", value=default_start)
        
        default_end = start_date + timedelta(days=10) if 'start_date' in locals() else datetime.now().date() + timedelta(days=17)
        end_date = st.date_input("Date de fin *", value=default_end)
        
     
        
        submitted = st.form_submit_button("🚀 Créer et Planifier Automatiquement", type="primary")
        
        if submitted:
            if not session_name or not start_date or not end_date:
                st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                return
            
            if start_date >= end_date:
                st.error("⚠️ La date de fin doit être après la date de début")
                return
            
            with st.spinner("⏳ Création et planification en cours... Cette opération peut prendre quelques secondes"):
                try:
                    if not ALGO_AVAILABLE:
                        st.error("❌ L'algorithme de planification n'est pas disponible")
                        return
                    
                    formations = fetch_formations()
                    if not formations:
                        st.error("❌ Aucune formation trouvée dans la base de données")
                        return
                    
                    formation_ids = [f['id'] for f in formations]
                    
                    results = create_session_and_generate_exams(
                        nom_session=session_name,
                        date_debut=start_date,
                        date_fin=end_date,
                        formation_ids=formation_ids
                    )
                    
                    st.session_state.creation_results = results
                    
                except Exception as e:
                    st.error(f"❌ Erreur lors de la création : {str(e)}")
    
    # Afficher les résultats
    if st.session_state.creation_results:
        results = st.session_state.creation_results
        
        if results['success']:
            st.success(f"✅ Session créée avec succès !")
            
            planning_results = results.get('planning_results')
            
            if planning_results and isinstance(planning_results, dict):
                if 'execution_time' in planning_results:
                    st.info(f"⏱️ Temps d'exécution : {planning_results['execution_time']} secondes")
                
                if 'message' in planning_results:
                    st.info(f"📋 {planning_results['message']}")
            
            else:
                st.warning("⚠️ La planification automatique n'a pas retourné de résultats détaillés")
            
        else:
            st.error(f"❌ Erreur : {results.get('message', 'Erreur inconnue')}")
    
    # Bouton pour réinitialiser
    if st.session_state.creation_results:
        if st.button("➕ Créer une nouvelle session"):
            st.session_state.creation_results = None
            st.rerun()

def show_existing_sessions():
    """Afficher les sessions existantes"""
    st.header("📋 Sessions d'examens existantes")
    
    if not ALGO_AVAILABLE:
        st.warning("⚠️ Impossible de charger les sessions")
        return
    
    sessions = fetch_sessions()
    
    if not sessions:
        st.info("ℹ️ Aucune session créée. Commencez par créer une nouvelle session.")
        return
    
    # Liste des sessions
    for session in sessions:
        with st.container():
            col1,  col3 = st.columns([4, 1])
            
            with col1:
                st.markdown(f"**{session['nom']}**")
                st.caption(f"📅 Du {session['date_debut']} au {session['date_fin']}")
                st.caption(f"📊 {session['nb_examens']} examens")
            
          
            with col3:
                if st.button("🔍 Voir", key=f"view_{session['id']}"):
                    st.session_state['selected_session'] = session['id']
                    st.rerun()
            
            st.divider()
    
    # Détails de la session sélectionnée
    if 'selected_session' in st.session_state:
        show_session_details(st.session_state['selected_session'])

def show_session_details(session_id):
    """Afficher les détails d'une session spécifique"""
   
    
    # AJOUTER UNE NOUVELLE SECTION AVEC DEUX BOUTONS
    
  
    st.subheader("🔄 Options de replanification")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Bouton pour replanifier seulement les examens non planifiés
        if st.button("🔄 Replanifier cette session", type="secondary", use_container_width=True):
            with st.spinner("Replanification en cours..."):
                results = planify_session_exams(session_id)
                if results['success']:
                    st.success(results['message'])
                    time.sleep(2)
                    st.rerun()
                else:
                    st.error(results['message'])
    
    
    
    # Récupérer les examens
    examens = fetch_examens_by_session_grouped(session_id)
    
    if not examens:
        st.info("ℹ️ Aucun examen trouvé pour cette session")
        return
    
    # Convertir en DataFrame
    df = pd.DataFrame(examens)
    
    if 'date_examen' in df.columns and df['date_examen'].notna().any():
        df['date_examen'] = pd.to_datetime(df['date_examen']).dt.date
    
 
    
    # Planning par formation et groupe
    st.subheader("📚 Planning détaillé par Formation et Groupe")
    
    if 'formation_nom' in df.columns and 'groupe_nom' in df.columns:
        formations_list = sorted(df['formation_nom'].unique())
        
        for formation in formations_list:
            st.markdown(f"#### 📖 {formation}")
            
            formation_exams = df[df['formation_nom'] == formation]
            groupes_list = sorted(formation_exams['groupe_nom'].unique())
            
            for groupe in groupes_list:
                with st.expander(f"👥 Groupe {groupe}", expanded=True):
                    groupe_exams = formation_exams[formation_exams['groupe_nom'] == groupe].copy()
                    
                    if 'date_examen' in groupe_exams.columns and 'heure_debut' in groupe_exams.columns:
                        groupe_exams = groupe_exams.sort_values(['date_examen', 'heure_debut'])
                    
                    groupe_columns = ['module_nom', 'date_examen', 'heure_debut', 'salle_nom', 'statut']
                    groupe_columns = [col for col in groupe_columns if col in groupe_exams.columns]
                    
                    if groupe_columns:
                        st.dataframe(
                            groupe_exams[groupe_columns],
                            column_config={
                                "module_nom": "Module",
                                "date_examen": "Date",
                                "heure_debut": "Heure",
                                "salle_nom": "Salle",
                                "statut": "Statut"
                            },
                            use_container_width=True,
                            hide_index=True
                        )
    
    # Export
    st.subheader("📤 Export des données")
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Télécharger en CSV",
        data=csv,
        file_name=f"session_{session_id}.csv",
        mime="text/csv",
        use_container_width=True
    )

def manage_salles():
    """Gestion des salles"""
    st.header("🏫 Gestion des Salles")
    
    # Onglets
    tab1, tab2 = st.tabs(["📋 Liste des Salles", "➕ Ajouter une Salle"])
    
    with tab1:
        salles = fetch_salles()
        if salles:
            df = pd.DataFrame(salles)
            st.dataframe(
                df,
                column_config={
                    "id": "ID",
                    "nom": "Nom",
                    "capacite": "Capacité",
                    "type": "Type"
                },
                use_container_width=True,
                hide_index=True
            )
            
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Nombre total de salles", len(salles))
                st.metric("Capacité totale", sum(s['capacite'] for s in salles))
            with col2:
                st.metric("Amphithéâtres", len([s for s in salles if s['type'] == 'AMPHI']))
                st.metric("Salles de cours", len([s for s in salles if s['type'] == 'SALLE']))
        else:
            st.info("ℹ️ Aucune salle trouvée")
    
    with tab2:
        with st.form("add_salle_form"):
            st.subheader("➕ Ajouter une nouvelle salle")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nom = st.text_input("Nom de la salle *", placeholder="Ex: Amphi A, Salle 101")
                type_salle = st.selectbox("Type *", ["SALLE", "AMPHI"])
            
            with col2:
                capacite = st.number_input("Capacité *", min_value=1, max_value=500, value=30)
            
            submitted = st.form_submit_button("➕ Ajouter la salle", type="primary")
            
            if submitted:
                if not nom or not capacite:
                    st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                else:
                    conn = get_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO salles (nom, capacite, type) VALUES (%s, %s, %s)",
                                (nom, capacite, type_salle)
                            )
                            conn.commit()
                            st.success(f"✅ Salle '{nom}' ajoutée avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {e}")
                        finally:
                            conn.close()
                    else:
                        st.error("❌ Impossible de se connecter à la base de données")

def manage_professeurs():
    """Gestion des professeurs"""
    st.header("👨‍🏫 Gestion des Professeurs")
    
    tab1, tab2 = st.tabs(["📋 Liste des Professeurs", "➕ Ajouter un Professeur"])
    
    with tab1:
        professeurs = fetch_professeurs()
        if professeurs:
            df = pd.DataFrame(professeurs)
            st.dataframe(
                df[['id', 'email', 'specialite', 'departement', 'is_active']],
                column_config={
                    "id": "ID",
                    "email": "Email",
                    "specialite": "Spécialité",
                    "departement": "Département",
                    "is_active": "Actif"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Aucun professeur trouvé")
    
    with tab2:
        with st.form("add_prof_form"):
            st.subheader("➕ Ajouter un nouveau professeur")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input("Email *", placeholder="ex: prof.nom@univ.dz")
                specialite = st.text_input("Spécialité *", placeholder="ex: Mathématiques")
            
            with col2:
                conn = get_connection()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT id, nom FROM departements")
                    departements = cursor.fetchall()
                    conn.close()
                    
                    departement_options = {d['nom']: d['id'] for d in departements}
                    departement_nom = st.selectbox("Département *", list(departement_options.keys()))
                    departement_id = departement_options.get(departement_nom)
                else:
                    st.error("❌ Impossible de charger les départements")
                    departement_id = None
            
            password = st.text_input("Mot de passe *", type="password")
            
            if password:
                is_valid, message = verify_password_strength(password)
                if not is_valid:
                    st.warning(f"⚠️ {message}")
            
            submitted = st.form_submit_button("➕ Ajouter le professeur", type="primary")
            
            if submitted:
                if not email or not specialite or not password or not departement_id:
                    st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                else:
                    is_valid, message = verify_password_strength(password)
                    if not is_valid:
                        st.error(f"❌ Mot de passe faible: {message}")
                    else:
                        user_id = create_user(email, password, 'PROF')
                        if user_id:
                            conn = get_connection()
                            if conn:
                                try:
                                    cursor = conn.cursor()
                                    cursor.execute(
                                        "INSERT INTO professeurs (user_id, departement_id, specialite) VALUES (%s, %s, %s)",
                                        (user_id, departement_id, specialite)
                                    )
                                    conn.commit()
                                    st.success(f"✅ Professeur '{email}' ajouté avec succès !")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"❌ Erreur: {e}")
                                finally:
                                    conn.close()
                        else:
                            st.error("❌ Erreur lors de la création de l'utilisateur")

def manage_etudiants():
    """Gestion des étudiants"""
    st.header("👨‍🎓 Gestion des Étudiants")
    
    tab1, tab2 = st.tabs(["📋 Liste des Étudiants", "➕ Ajouter un Étudiant"])
    
    with tab1:
        etudiants = fetch_etudiants()
        if etudiants:
            df = pd.DataFrame(etudiants)
            st.dataframe(
                df,
                column_config={
                    "id": "ID",
                    "email": "Email",
                    "groupe_id": "Groupe ID"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Aucun étudiant trouvé")
    
    with tab2:
        with st.form("add_etudiant_form"):
            st.subheader("➕ Ajouter un nouvel étudiant")
            
            col1, col2 = st.columns(2)
            
            with col1:
                email = st.text_input("Email *", placeholder="ex: etudiant.nom@univ.dz")
                matricule = st.text_input("Matricule *", placeholder="ex: 20240001")
                nom = st.text_input("Nom *")
                prenom = st.text_input("Prénom *")
            
            with col2:
                conn = get_connection()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT id, nom, formation_id FROM groupes")
                    groupes = cursor.fetchall()
                    conn.close()
                    
                    groupe_options = {}
                    for g in groupes:
                        conn2 = get_connection()
                        cursor2 = conn2.cursor(dictionary=True)
                        cursor2.execute("SELECT nom FROM formations WHERE id = %s", (g['formation_id'],))
                        formation = cursor2.fetchone()
                        conn2.close()
                        
                        formation_nom = formation['nom'] if formation else "Inconnu"
                        label = f"{g['nom']} ({formation_nom})"
                        groupe_options[label] = g['id']
                    
                    groupe_label = st.selectbox("Groupe *", list(groupe_options.keys()))
                    groupe_id = groupe_options.get(groupe_label)
                else:
                    st.error("❌ Impossible de charger les groupes")
                    groupe_id = None
            
            password = st.text_input("Mot de passe *", type="password")
            
            submitted = st.form_submit_button("➕ Ajouter l'étudiant", type="primary")
            
            if submitted:
                if not email or not matricule or not nom or not prenom or not password or not groupe_id:
                    st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                else:
                    user_id = create_user(email, password, 'ETUDIANT')
                    if user_id:
                        conn = get_connection()
                        if conn:
                            try:
                                cursor = conn.cursor()
                                cursor.execute(
                                    "INSERT INTO etudiants (user_id, nom, prenom, matricule, groupe_id) VALUES (%s, %s, %s, %s, %s)",
                                    (user_id, nom, prenom, matricule, groupe_id)
                                )
                                conn.commit()
                                st.success(f"✅ Étudiant '{nom} {prenom}' ajouté avec succès !")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Erreur: {e}")
                            finally:
                                conn.close()
                    else:
                        st.error("❌ Erreur lors de la création de l'utilisateur")

def manage_modules_formations():
    """Gestion des modules et formations"""
    st.header("📚 Gestion des Modules et Formations")
    
    tab1, tab2, tab3 = st.tabs(["📋 Formations", "➕ Ajouter Formation", "📘 Gestion Modules"])
    
    with tab1:
        formations = fetch_formations()
        if formations:
            df = pd.DataFrame(formations)
            st.dataframe(
                df,
                column_config={
                    "id": "ID",
                    "nom": "Nom",
                    "departement": "Département"
                },
                use_container_width=True,
                hide_index=True
            )
        else:
            st.info("ℹ️ Aucune formation trouvée")
    
    with tab2:
        with st.form("add_formation_form"):
            st.subheader("➕ Ajouter une nouvelle formation")
            
            nom = st.text_input("Nom de la formation *", placeholder="ex: Informatique L1")
            
            conn = get_connection()
            if conn:
                cursor = conn.cursor(dictionary=True)
                cursor.execute("SELECT id, nom FROM departements")
                departements = cursor.fetchall()
                conn.close()
                
                departement_options = {d['nom']: d['id'] for d in departements}
                departement_nom = st.selectbox("Département *", list(departement_options.keys()))
                departement_id = departement_options.get(departement_nom)
            else:
                st.error("❌ Impossible de charger les départements")
                departement_id = None
            
            submitted = st.form_submit_button("➕ Ajouter la formation", type="primary")
            
            if submitted:
                if not nom or not departement_id:
                    st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                else:
                    conn = get_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO formations (nom, departement_id) VALUES (%s, %s)",
                                (nom, departement_id)
                            )
                            conn.commit()
                            st.success(f"✅ Formation '{nom}' ajoutée avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {e}")
                        finally:
                            conn.close()
    
    with tab3:
        st.subheader("📘 Gestion des Modules")
        
        conn = get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT m.id, m.nom, f.nom as formation_nom 
                FROM modules m
                JOIN formations f ON m.formation_id = f.id
                ORDER BY f.nom, m.nom
            """)
            modules = cursor.fetchall()
            
            if modules:
                df_modules = pd.DataFrame(modules)
                st.dataframe(
                    df_modules,
                    column_config={
                        "id": "ID",
                        "nom": "Nom du module",
                        "formation_nom": "Formation"
                    },
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("ℹ️ Aucun module trouvé")
            
            st.subheader("➕ Ajouter un nouveau module")
            with st.form("add_module_form"):
                col1, col2 = st.columns(2)
                
                with col1:
                    module_nom = st.text_input("Nom du module *", placeholder="ex: Algorithmique")
                
                with col2:
                    cursor.execute("SELECT id, nom FROM formations")
                    formations_list = cursor.fetchall()
                    formation_options = {f['nom']: f['id'] for f in formations_list}
                    formation_nom = st.selectbox("Formation *", list(formation_options.keys()))
                    formation_id = formation_options.get(formation_nom)
                
                submitted_module = st.form_submit_button("➕ Ajouter le module", type="primary")
                
                if submitted_module:
                    if not module_nom or not formation_id:
                        st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                    else:
                        try:
                            cursor.execute(
                                "INSERT INTO modules (nom, formation_id) VALUES (%s, %s)",
                                (module_nom, formation_id)
                            )
                            conn.commit()
                            st.success(f"✅ Module '{module_nom}' ajouté avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {e}")
            
            conn.close()
        else:
            st.error("❌ Impossible de se connecter à la base de données")

def manage_groupes():
    """Gestion des groupes"""
    st.header("👥 Gestion des Groupes")
    
    tab1, tab2 = st.tabs(["📋 Liste des Groupes", "➕ Ajouter un Groupe"])
    
    with tab1:
        conn = get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("""
                SELECT g.id, g.nom, g.effectif, f.nom as formation_nom
                FROM groupes g
                JOIN formations f ON g.formation_id = f.id
                ORDER BY f.nom, g.nom
            """)
            groupes = cursor.fetchall()
            conn.close()
            
            if groupes:
                df = pd.DataFrame(groupes)
                st.dataframe(
                    df,
                    column_config={
                        "id": "ID",
                        "nom": "Nom",
                        "effectif": "Effectif",
                        "formation_nom": "Formation"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Nombre total de groupes", len(groupes))
                with col2:
                    st.metric("Effectif total", sum(g['effectif'] for g in groupes))
            else:
                st.info("ℹ️ Aucun groupe trouvé")
        else:
            st.error("❌ Impossible de se connecter à la base de données")
    
    with tab2:
        with st.form("add_groupe_form"):
            st.subheader("➕ Ajouter un nouveau groupe")
            
            col1, col2 = st.columns(2)
            
            with col1:
                nom = st.text_input("Nom du groupe *", placeholder="ex: G1, G2, TD1")
                effectif = st.number_input("Effectif *", min_value=1, max_value=200, value=30)
            
            with col2:
                conn = get_connection()
                if conn:
                    cursor = conn.cursor(dictionary=True)
                    cursor.execute("SELECT id, nom FROM formations")
                    formations = cursor.fetchall()
                    conn.close()
                    
                    formation_options = {f['nom']: f['id'] for f in formations}
                    formation_nom = st.selectbox("Formation *", list(formation_options.keys()))
                    formation_id = formation_options.get(formation_nom)
                else:
                    st.error("❌ Impossible de charger les formations")
                    formation_id = None
            
            submitted = st.form_submit_button("➕ Ajouter le groupe", type="primary")
            
            if submitted:
                if not nom or not effectif or not formation_id:
                    st.error("⚠️ Veuillez remplir tous les champs obligatoires (*)")
                else:
                    conn = get_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO groupes (nom, formation_id, effectif) VALUES (%s, %s, %s)",
                                (nom, formation_id, effectif)
                            )
                            conn.commit()
                            st.success(f"✅ Groupe '{nom}' ajouté avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {e}")
                        finally:
                            conn.close()

def manage_departements():
    """Gestion des départements"""
    st.header("🏢 Gestion des Départements")
    
    tab1, tab2 = st.tabs(["📋 Liste des Départements", "➕ Ajouter un Département"])
    
    with tab1:
        conn = get_connection()
        if conn:
            cursor = conn.cursor(dictionary=True)
            cursor.execute("SELECT id, nom FROM departements ORDER BY nom")
            departements = cursor.fetchall()
            conn.close()
            
            if departements:
                df = pd.DataFrame(departements)
                st.dataframe(
                    df,
                    column_config={
                        "id": "ID",
                        "nom": "Nom du département"
                    },
                    use_container_width=True,
                    hide_index=True
                )
                
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT d.nom, COUNT(f.id) as nb_formations
                    FROM departements d
                    LEFT JOIN formations f ON d.id = f.departement_id
                    GROUP BY d.id
                    ORDER BY d.nom
                """)
                stats = cursor.fetchall()
                conn.close()
                
                st.subheader("📊 Statistiques par département")
                for stat in stats:
                    st.write(f"**{stat['nom']}**: {stat['nb_formations']} formation(s)")
            else:
                st.info("ℹ️ Aucun département trouvé")
        else:
            st.error("❌ Impossible de se connecter à la base de données")
    
    with tab2:
        with st.form("add_departement_form"):
            st.subheader("➕ Ajouter un nouveau département")
            
            nom = st.text_input("Nom du département *", placeholder="ex: Informatique, Mathématiques")
            
            submitted = st.form_submit_button("➕ Ajouter le département", type="primary")
            
            if submitted:
                if not nom:
                    st.error("⚠️ Veuillez remplir le nom du département")
                else:
                    conn = get_connection()
                    if conn:
                        try:
                            cursor = conn.cursor()
                            cursor.execute(
                                "INSERT INTO departements (nom) VALUES (%s)",
                                (nom,)
                            )
                            conn.commit()
                            st.success(f"✅ Département '{nom}' ajouté avec succès !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"❌ Erreur: {e}")
                        finally:
                            conn.close()


if __name__ == "__main__":
    show_dashboard()