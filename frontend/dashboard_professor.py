# frontend/dashboard_professor.py
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


def show_professor_dashboard():
    """Dashboard professeur – Mes Surveillance et Mon Profil"""

    user = st.session_state.user

    # ================== SIDEBAR ==================
    with st.sidebar:
        # Infos professeur
        if DB_AVAILABLE:
            try:
                conn = get_connection()
                cursor = conn.cursor(dictionary=True)
                cursor.execute("""
                    SELECT p.specialite,
                           d.nom AS departement,
                           p.nb_max_surveillances_jour,
                           p.heures_semaine_max
                    FROM professeurs p
                    JOIN departements d ON p.departement_id = d.id
                    WHERE p.user_id = %s
                """, (user['id'],))
                info = cursor.fetchone()
                cursor.close()
                conn.close()

                if info:
                    st.write(f"🎓 **Spécialité :** {info['specialite']}")
                    st.write(f"🏢 **Département :** {info['departement']}")
                    st.write(f"📊 **Limite/jour :** {info['nb_max_surveillances_jour']}")
            except Exception as e:
                st.error(f"Erreur: {e}")

        st.write("---")

        st.markdown("### 📋 Menu")
        
        menu_option = st.radio(
            "Navigation",
            ["📋 Mes Surveillance", "👤 Mon Profil"]
        )

        st.write("---")
        if st.button("🚪 Déconnexion", use_container_width=True):
            del st.session_state.user
            st.rerun()

    # ================== CONTENU ==================
    st.title("👨‍🏫 Espace Professeur")
    st.markdown("---")
    
    if menu_option == "📋 Mes Surveillance":
        show_surveillance(user)
    elif menu_option == "👤 Mon Profil":
        show_professor_profile(user)


def show_surveillance(user):
    """Afficher les surveillances CONFIRMÉES et PLANIFIÉES du professeur"""
    st.header("📋 Mes Surveillance")
    
    if not DB_AVAILABLE:
        st.error("❌ Base de données non disponible")
        return
    
    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Récupérer l'ID du professeur
        cursor.execute("SELECT id FROM professeurs WHERE user_id = %s", (user['id'],))
        prof_info = cursor.fetchone()
        
        if not prof_info:
            st.error("❌ Profil professeur non trouvé")
            return
        
        prof_id = prof_info['id']
        
        # Récupérer uniquement les surveillances CONFIRMÉES et PLANIFIÉES (avec date)
        cursor.execute("""
    SELECT DISTINCT
        e.id as examen_id,
        m.nom as module_nom,
        f.nom as formation_nom,
        g.nom as groupe_nom,
        g.effectif,
        se.nom as session_nom,
        s.date_surveillance,
        s.heure_debut,
        e.duree_minutes,
        COALESCE(s.salle_id, e.salle_id) as salle_id,  -- Prendre soit la salle de surveillance, soit celle de l'examen
        COALESCE(sa.nom, sa2.nom) as salle_nom,        -- Nom correspondant
        COUNT(DISTINCT s.prof_id) as nb_surveillants
    FROM surveillances s
    JOIN examens e ON s.examen_id = e.id
    JOIN modules m ON e.module_id = m.id
    JOIN formations f ON e.formation_id = f.id
    JOIN groupes g ON e.groupe_id = g.id
    JOIN sessions_examens se ON e.session_id = se.id
    LEFT JOIN salles sa ON s.salle_id = sa.id  -- Salle spécifique à la surveillance
    LEFT JOIN salles sa2 ON e.salle_id = sa2.id  -- Salle assignée à l'examen
    WHERE s.prof_id = %s
    AND e.statut = 'CONFIRME'
    AND s.date_surveillance IS NOT NULL
    GROUP BY e.id, m.nom, f.nom, g.nom, g.effectif, se.nom, 
             s.date_surveillance, s.heure_debut, e.duree_minutes,
             COALESCE(s.salle_id, e.salle_id),
             COALESCE(sa.nom, sa2.nom)
    ORDER BY s.date_surveillance, s.heure_debut
""", (prof_id,))
        
        surveillances = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        if not surveillances:
            st.info("📭 Aucune surveillance planifiée pour le moment.")
            return
        
        # Statistiques
        total_surv = len(surveillances)
        
        st.metric("Total surveillances planifiées", total_surv)
        st.markdown("---")
        
        # Préparer les données pour le tableau
        surv_data = []
        for surv in surveillances:
            # Calculer l'heure de fin
            heure_debut = surv['heure_debut']
            duree = surv['duree_minutes']
            heure_str = "-"
            
            if heure_debut:
                # Gérer à la fois les strings et les timedelta
                if isinstance(heure_debut, str):
                    # C'est un string "HH:MM:SS"
                    heure_debut_time = heure_debut_obj.time()
                    total_minutes = heure_debut_time.hour * 60 + heure_debut_time.minute + duree
                    heure_debut_str = heure_debut_obj.strftime('%H:%M')
                    
                    # Calcul de l'heure de fin
                    total_minutes = heure_debut_obj.hour * 60 + heure_debut_obj.minute + duree
                else:
                    # C'est un timedelta, convertir en heures:minutes
                    total_seconds = heure_debut.total_seconds()
                    hours = int(total_seconds // 3600)
                    minutes = int((total_seconds % 3600) // 60)
                    heure_debut_str = f"{hours:02d}:{minutes:02d}"
                    
                    # Calcul de l'heure de fin en minutes depuis minuit
                    total_minutes = hours * 60 + minutes + duree
                
                # Calcul de l'heure de fin
                heure_fin_hour = (total_minutes // 60) % 24
                heure_fin_minute = total_minutes % 60
                heure_fin_str = f"{heure_fin_hour:02d}:{heure_fin_minute:02d}"
                
                heure_str = f"{heure_debut_str} - {heure_fin_str}"
            
            surv_info = {
                "📚 Module": surv['module_nom'],
                "📅 Date": surv['date_surveillance'].strftime("%d/%m/%Y"),
                "🕐 Horaire": heure_str,
                "🏫 Salle": surv['salle_nom'] or "Non assignée",
                "👥 Groupe": surv['groupe_nom'] or "-",
                "📋 Session": surv['session_nom'] or "-",
                "👥 Effectif": surv['effectif'] or 0
            }
            surv_data.append(surv_info)
        
        # Afficher le tableau
        st.dataframe(
            surv_data,
            use_container_width=True,
            hide_index=True
        )
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des surveillances : {str(e)}")


def show_professor_profile(user):
    """Affichage et gestion du profil professeur"""

    st.header("👤 Mon Profil")

    if not DB_AVAILABLE:
        st.error("❌ Base de données non disponible")
        return

    try:
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Récupérer les informations du professeur
        cursor.execute("""
            SELECT 
                u.email,
                u.role,
                u.is_active,
                p.specialite,
                d.nom AS departement,
                p.nb_max_surveillances_jour,
                p.heures_semaine_max
            FROM users u
            JOIN professeurs p ON u.id = p.user_id
            JOIN departements d ON p.departement_id = d.id
            WHERE u.id = %s
        """, (user['id'],))

        data = cursor.fetchone()

        if not data:
            st.warning("Aucune information trouvée")
            return

        # Affichage en deux colonnes
        col1, col2 = st.columns(2)

        with col1:
            st.info(f"**Email :** {data['email']}")
            st.info(f"**Rôle :** {data['role']}")
            st.info(f"**Spécialité :** {data['specialite']}")

        with col2:
            st.info(f"**Département :** {data['departement']}")
            st.info(f"**Statut :** {'Actif' if data['is_active'] == 1 else 'Inactif'}")
            st.info(f"**Limite surveillances/jour :** {data['nb_max_surveillances_jour']}")

        st.markdown("---")
        
        # Statistiques du professeur
        st.subheader("📊 Mes statistiques")
        
        # Compter les surveillances confirmées et planifiées
        cursor.execute("""
            SELECT COUNT(*) as total_surv
            FROM surveillances s
            JOIN examens e ON s.examen_id = e.id
            JOIN professeurs p ON s.prof_id = p.id
            WHERE p.user_id = %s
            AND e.statut = 'CONFIRME'
            AND s.date_surveillance IS NOT NULL
        """, (user['id'],))
        
        stats = cursor.fetchone()
        total_surv = stats['total_surv'] if stats else 0
        
        st.metric("Surveillances planifiées (total)", total_surv)

        st.markdown("---")
        
        # Changer le mot de passe
        st.subheader("🔐 Changer mon mot de passe")

        with st.form("prof_pwd_form"):
            old = st.text_input("Ancien mot de passe", type="password")
            new = st.text_input("Nouveau mot de passe", type="password")
            confirm = st.text_input("Confirmer le mot de passe", type="password")

            submit = st.form_submit_button("Changer le mot de passe", use_container_width=True)

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
                            st.success("✅ Mot de passe modifié avec succès")
                        else:
                            st.error("❌ Erreur lors de la mise à jour")

        cursor.close()
        conn.close()

    except Exception as e:
        st.error(f"Erreur: {str(e)}")


if __name__ == "__main__":
    # Simulation d'un utilisateur professeur pour le test
    st.session_state.user = {
        'id': 4,
        'email': 'prof.ahmed@univ.dz',
        'role': 'PROF'
    }
    
    show_professor_dashboard()