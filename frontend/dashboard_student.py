import streamlit as st
import sys
import os
from datetime import datetime

# Import backend
backend_path = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.append(backend_path)

try:
    from backend.database import (
        get_connection,
        hash_password,
        verify_password_strength,
        update_user_password
    )
    DB_AVAILABLE = True
except ImportError as e:
    st.error(f"Erreur d'import backend : {e}")
    DB_AVAILABLE = False


def show_student_dashboard():
    """Dashboard étudiant – Mon Profil et Mes Examens"""

    user = st.session_state.user

    # ================== SIDEBAR ==================
    with st.sidebar:
        # Infos étudiant
        if DB_AVAILABLE:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT g.nom AS groupe_nom,
                           f.nom AS formation,
                           d.nom AS departement
                    FROM etudiants e
                    JOIN groupes g ON e.groupe_id = g.id
                    JOIN formations f ON g.formation_id = f.id
                    JOIN departements d ON f.departement_id = d.id
                    WHERE e.user_id = %s
                """, (user['id'],))
                info = cursor.fetchone()
                cursor.close()
                conn.close()

                if info:
                    st.write(f"🎓 **Formation :** {info['formation']}")
                    st.write(f"👥 **Groupe :** {info['groupe_nom']}")
                    st.write(f"🏢 **Département :** {info['departement']}")
            except:
                pass

        st.write("---")

        st.markdown("### 📋 Menu")
        
        menu_option = st.radio(
            "Navigation",
            ["📝 Mes Examens", "👤 Mon Profil"]
        )

        st.write("---")
        if st.button("🚪 Déconnexion", use_container_width=True):
            del st.session_state.user
            st.rerun()

    # ================== CONTENU ==================
    st.title("👨‍🎓 Espace Étudiant")
    st.markdown("---")
    
    if menu_option == "📝 Mes Examens":
        show_student_exams(user)
    elif menu_option == "👤 Mon Profil":
        show_student_profile(user)


def show_student_exams(user):
    """Afficher les examens CONFIRMÉS de l'étudiant selon son groupe"""
    st.header("📝 Mes Examens")
    
    if not DB_AVAILABLE:
        st.error("❌ Base de données non disponible")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 1. Récupérer les informations de l'étudiant (groupe et formation)
        cursor.execute("""
            SELECT e.groupe_id, g.nom as groupe_nom, g.formation_id, 
                   f.nom as formation_nom, d.nom as departement_nom
            FROM etudiants e
            JOIN groupes g ON e.groupe_id = g.id
            JOIN formations f ON g.formation_id = f.id
            JOIN departements d ON f.departement_id = d.id
            WHERE e.user_id = %s
        """, (user['id'],))
        
        student_info = cursor.fetchone()
        
        if not student_info:
            st.warning("Informations étudiant non trouvées")
            return
        
        groupe_id = student_info['groupe_id']
        groupe_nom = student_info['groupe_nom']
        formation_id = student_info['formation_id']
        formation_nom = student_info['formation_nom']
        
        st.info(f"**Formation :** {formation_nom} | **Groupe :** {groupe_nom}")
        
        # 2. Récupérer uniquement les examens CONFIRMÉS de son groupe
        cursor.execute("""
            SELECT e.*, 
                   m.nom as module_nom,
                   f.nom as formation_nom,
                   s.nom as salle_nom,
                   g.nom as groupe_nom,
                   se.nom as session_nom,
                   u.email as professeur_surveillant
            FROM examens e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON e.formation_id = f.id
            JOIN groupes g ON e.groupe_id = g.id
            JOIN sessions_examens se ON e.session_id = se.id
            LEFT JOIN salles s ON e.salle_id = s.id
            LEFT JOIN surveillances sv ON e.id = sv.examen_id
            LEFT JOIN professeurs p ON sv.prof_id = p.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE e.groupe_id = %s 
            AND e.statut = 'CONFIRME'  -- SEULEMENT LES EXAMENS CONFIRMÉS
            ORDER BY 
                CASE 
                    WHEN e.date_examen IS NULL THEN 1
                    ELSE 0
                END,
                e.date_examen,
                e.heure_debut
        """, (groupe_id,))
        
        exams = cursor.fetchall()
        
        if not exams:
            st.info("📭 Aucun examen confirmé pour votre groupe pour le moment.")
            
            # Option: Afficher les modules de la formation (pour information)
            with st.expander("📚 Voir les modules de votre formation"):
                cursor.execute("""
                    SELECT m.nom as module_nom
                    FROM modules m
                    WHERE m.formation_id = %s
                    ORDER BY m.nom
                """, (formation_id,))
                
                modules = cursor.fetchall()
                
                if modules:
                    st.write("**Modules de votre formation :**")
                    for module in modules:
                        st.write(f"• {module['module_nom']}")
                else:
                    st.write("Aucun module trouvé pour cette formation.")
            return
        
        # 3. Statistiques (uniquement pour les examens confirmés)
        total_exams = len(exams)
        exams_scheduled = len([e for e in exams if e['date_examen'] is not None])
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Total examens confirmés", total_exams)
        with col2:
            st.metric("Planifiés", exams_scheduled)
        
        st.markdown("---")
        
        # 4. Séparer les examens planifiés et non planifiés
        scheduled_exams = [e for e in exams if e['date_examen'] is not None]
        unscheduled_exams = [e for e in exams if e['date_examen'] is None]
        
        # 5. Afficher d'abord les examens planifiés (avec date)
        if scheduled_exams:
            # Trier par date et heure
            scheduled_exams.sort(key=lambda x: (x['date_examen'], x['heure_debut'] or datetime.min.time()))
            
            st.subheader("📅 Examens planifiés")
            
            # Préparer les données pour le tableau
            exam_data = []
            for exam in scheduled_exams:
                exam_info = {
                    "📚 Module": exam['module_nom'],
                    "📅 Date": exam['date_examen'].strftime("%d/%m/%Y"),
                    "🕐 Heure": str(exam['heure_debut'])[:5] if exam['heure_debut'] else "-",
                    "🏫 Salle": exam['salle_nom'] or "Non assignée",
                  
                }
                exam_data.append(exam_info)
            
            # Afficher le tableau
            st.dataframe(
                exam_data,
                use_container_width=True,
                hide_index=True
            )
            
            # Vue détaillée
            
        # 6. Afficher les examens confirmés mais non planifiés (sans date)
        if unscheduled_exams:
            st.markdown("---")
            st.subheader("⏳ Examens confirmés (en attente de planification)")
            
            # Préparer les données pour le tableau
            unscheduled_data = []
            for exam in unscheduled_exams:
                exam_info = {
                    "📚 Module": exam['module_nom'],
                    "📅 Date": "À définir",
                    "🕐 Heure": "À définir",
                    "🏫 Salle": "À définir",
                    "👨‍🏫 Surveillant": "À définir"
                }
                unscheduled_data.append(exam_info)
            
            # Afficher le tableau
            st.dataframe(
                unscheduled_data,
                use_container_width=True,
                hide_index=True
            )
            
            st.info("ℹ️ Ces examens sont confirmés mais pas encore planifiés. Les dates et salles seront communiquées ultérieurement.")
        
        # 7. Résumé
        st.markdown("---")
        today = datetime.now().date()
        
      
    except Exception as e:
        st.error(f"Erreur lors du chargement des examens : {str(e)}")


def show_student_profile(user):
    """Affichage et gestion du profil étudiant"""

    st.header("👤 Mon Profil")

    if not DB_AVAILABLE:
        st.error("❌ Base de données non disponible")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        cursor.execute("""
            SELECT 
                u.email,
                e.nom,
                e.prenom,
                e.matricule,
                g.nom AS groupe,
                f.nom AS formation,
                d.nom AS departement
            FROM users u
            JOIN etudiants e ON u.id = e.user_id
            JOIN groupes g ON e.groupe_id = g.id
            JOIN formations f ON g.formation_id = f.id
            JOIN departements d ON f.departement_id = d.id
            WHERE u.id = %s
        """, (user['id'],))

        data = cursor.fetchone()

        if not data:
            st.warning("Aucune information trouvée")
            return

        col1, col2 = st.columns(2)

        with col1:
            st.info(f"**Nom :** {data['nom']}")
            st.info(f"**Prénom :** {data['prenom']}")
            st.info(f"**Matricule :** {data['matricule']}")
            st.info(f"**Email :** {data['email']}")

        with col2:
            st.info(f"**Formation :** {data['formation']}")
            st.info(f"**Groupe :** {data['groupe']}")
            st.info(f"**Département :** {data['departement']}")

        st.markdown("---")
        st.subheader("🔐 Changer mon mot de passe")

        with st.form(f"pwd_form_{user['id']}"):
            old = st.text_input("Ancien mot de passe", type="password")
            new = st.text_input("Nouveau mot de passe", type="password")
            confirm = st.text_input("Confirmer le mot de passe", type="password")

            submit = st.form_submit_button("Changer le mot de passe")

            if submit:
                if not old or not new or not confirm:
                    st.error("Tous les champs sont obligatoires")
                elif new != confirm:
                    st.error("Les mots de passe ne correspondent pas")
                else:
                    valid, msg = verify_password_strength(new)
                    if not valid:
                        st.error(msg)
                    else:
                        success = update_user_password(user['id'], new)
                        if success:
                            st.success("Mot de passe modifié avec succès")
                        else:
                            st.error("Erreur lors de la mise à jour")

        cursor.close()
        conn.close()

    except Exception as e:
        st.error(str(e))


if __name__ == "__main__":
   
    show_student_dashboard()