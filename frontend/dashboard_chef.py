
import streamlit as st
from backend.database import get_connection

def show_chef_dashboard():
    """Dashboard spécifique au Chef de Département"""
    user = st.session_state.user
    
    st.title("🏢 Tableau de Bord - Chef de Département")
    
    # Barre latérale
    with st.sidebar:
        st.image("https://cdn-icons-png.flaticon.com/512/3135/3135715.png", width=100)
        st.write(f"**👤 {user.get('email', 'Utilisateur')}**")
        st.write(f"**🎯 Rôle: Chef de Département**")
        st.divider()
        
        menu_option = st.radio(
            "Menu",
            ["📋 Validation Examens", "📊 Statistiques"]
        )
        
        st.divider()
        if st.button("🚪 Déconnexion"):
            del st.session_state.user
            st.rerun()
    
    # Contenu principal
    if menu_option == "📋 Validation Examens":
        show_validation_section(user)
    elif menu_option == "📊 Statistiques":
        show_statistics_section(user)

def show_validation_section(user):
    """Section de validation des examens par département avec tableau tabulaire"""
    st.header("📋 Validation des Examens")
    
    conn = get_connection()
    if not conn:
        st.error("Impossible de se connecter à la base de données")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Récupérer le département du chef
        email = user['email']
        
        # Chercher le département du chef dans la table users
        cursor.execute("""
            SELECT u.departement_id, d.nom as departement_nom
            FROM users u
            LEFT JOIN departements d ON u.departement_id = d.id
            WHERE u.email = %s AND u.role = 'CHEF_DEPT'
        """, (email,))
        
        dept_info = cursor.fetchone()
        
        if not dept_info or not dept_info['departement_id']:
            st.error("❌ Vous n'êtes pas associé à un département. Contactez l'administrateur.")
            return
        
        dept_id = dept_info['departement_id']
        dept_nom = dept_info['departement_nom']
        
        st.info(f"👨‍💼 Chef du Département: **{dept_nom}**")
        
        # Filtrer par session
        cursor.execute("""
            SELECT DISTINCT s.id, s.nom, s.date_debut, s.date_fin
            FROM sessions_examens s
            JOIN examens e ON s.id = e.session_id
            JOIN formations f ON e.formation_id = f.id
            WHERE f.departement_id = %s
            ORDER BY s.date_debut DESC
        """, (dept_id,))
        
        sessions = cursor.fetchall()
        
        if not sessions:
            st.info("📭 Aucune session d'examens pour votre département")
            return
        
        # Sélectionner une session
        session_options = {f"{s['nom']} ({s['date_debut']} au {s['date_fin']})": s['id'] for s in sessions}
        selected_session_label = st.selectbox(
            "Sélectionnez une session:",
            list(session_options.keys())
        )
        
        if not selected_session_label:
            return
        
        session_id = session_options[selected_session_label]
        
        # Afficher les filtres de statut
        col1, col2, col3 = st.columns(3)
        with col1:
            show_all = st.checkbox("Afficher tous", value=True)
        with col2:
            show_pending = st.checkbox("En attente", value=True)
        with col3:
            show_confirmed = st.checkbox("Confirmés", value=False)
        
        # Construire la requête selon les filtres
        statut_conditions = []
        if show_all or show_pending:
            statut_conditions.append("'EN_ATTENTE'")
        if show_all or show_confirmed:
            statut_conditions.append("'CONFIRME'")
        
        if not statut_conditions:
            st.warning("Sélectionnez au moins un statut à afficher")
            return
        
        statut_list = ','.join(statut_conditions)
        
        # Récupérer les examens
        query = f"""
            SELECT e.*, 
                   m.nom as module_nom, 
                   f.nom as formation_nom,
                   s.nom as salle_nom,
                   g.nom as groupe_nom,
                   g.effectif as groupe_effectif,
                   se.nom as session_nom,
                   u.email as professeur_email,
                   e.date_examen,
                   e.heure_debut,
                   e.duree_minutes
            FROM examens e
            JOIN modules m ON e.module_id = m.id
            JOIN formations f ON e.formation_id = f.id
            JOIN groupes g ON e.groupe_id = g.id
            JOIN sessions_examens se ON e.session_id = se.id
            LEFT JOIN salles s ON e.salle_id = s.id
            LEFT JOIN surveillances sv ON e.id = sv.examen_id
            LEFT JOIN professeurs p ON sv.prof_id = p.id
            LEFT JOIN users u ON p.user_id = u.id
            WHERE e.session_id = %s
            AND f.departement_id = %s
            AND e.statut IN ({statut_list})
            ORDER BY 
                f.nom,
                g.nom,
                e.date_examen,
                e.heure_debut
        """
        
        cursor.execute(query, (session_id, dept_id))
        examens = cursor.fetchall()
        
        if not examens:
            st.info("📭 Aucun examen correspondant aux critères sélectionnés")
            return
        
        # Afficher les statistiques
        total_examens = len(examens)
        examens_attente = len([e for e in examens if e['statut'] == 'EN_ATTENTE'])
        examens_confirme = len([e for e in examens if e['statut'] == 'CONFIRME'])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total examens", total_examens)
        with col2:
            st.metric("En attente", examens_attente, 
                     delta=f"{examens_attente}/{total_examens}")
        with col3:
            st.metric("Confirmés", examens_confirme,
                     delta=f"{examens_confirme}/{total_examens}")
        
        # Afficher le tableau des examens
        st.subheader("📝 Tableau des Examens")
        
        # Préparer les données pour le tableau
        import pandas as pd
        
        table_data = []
        
        for examen in examens:
            # Formater la date si elle existe
            date_formatted = ""
            if examen['date_examen']:
                # Convertir en objet date puis formater
                from datetime import datetime
                if isinstance(examen['date_examen'], str):
                    try:
                        date_obj = datetime.strptime(examen['date_examen'], '%Y-%m-%d').date()
                    except:
                        date_obj = datetime.strptime(examen['date_examen'], '%Y-%m-%d %H:%M:%S').date()
                else:
                    date_obj = examen['date_examen']
                date_formatted = date_obj.strftime('%d/%m/%Y')
            
            # Formater l'heure si elle existe (convertir secondes en HH:MM)
            heure_formatted = ""
            if examen['heure_debut']:
                try:
                    # Si l'heure est stockée comme secondes depuis minuit
                    if isinstance(examen['heure_debut'], (int, float)):
                        # Convertir secondes en HH:MM
                        total_seconds = int(examen['heure_debut'])
                        hours = total_seconds // 3600
                        minutes = (total_seconds % 3600) // 60
                        heure_formatted = f"{hours:02d}:{minutes:02d}"
                    # Si c'est déjà une chaîne de caractères (format TIME)
                    elif isinstance(examen['heure_debut'], str):
                        # Essayer différents formats
                        if ':' in examen['heure_debut']:
                            # Si c'est déjà en HH:MM:SS, prendre seulement HH:MM
                            time_parts = examen['heure_debut'].split(':')
                            if len(time_parts) >= 2:
                                heure_formatted = f"{time_parts[0]}:{time_parts[1]}"
                        else:
                            # Si c'est un nombre en secondes comme chaîne
                            total_seconds = int(float(examen['heure_debut']))
                            hours = total_seconds // 3600
                            minutes = (total_seconds % 3600) // 60
                            heure_formatted = f"{hours:02d}:{minutes:02d}"
                    else:
                        heure_formatted = str(examen['heure_debut'])
                except Exception as e:
                    print(f"Erreur de conversion heure: {e}")
                    heure_formatted = str(examen['heure_debut'])
            
            # Déterminer l'icône de statut
            statut_icon = ""
            if examen['statut'] == 'EN_ATTENTE':
                statut_icon = "⏳"
            elif examen['statut'] == 'CONFIRME':
                statut_icon = "✅"
            elif examen['statut'] == 'REFUSE':
                statut_icon = "❌"
            
            table_data.append({
                "Formation": examen['formation_nom'],
                "Groupe": examen['groupe_nom'],
                "Module": examen['module_nom'],
                "Date": date_formatted,
                "Heure": heure_formatted,
                "Salle": examen['salle_nom'] or "Non assignée",
                "Surveillant": examen['professeur_email'] or "Non assigné",
                "Durée": f"{examen['duree_minutes']} min",
                "Statut": f"{statut_icon} {examen['statut']}",
                "ID": examen['id']  # Garder l'ID pour les actions
            })
        
        # Créer le DataFrame
        df_examens = pd.DataFrame(table_data)
        
        # Afficher le tableau avec Streamlit
        st.dataframe(
            df_examens,
            column_config={
                "Formation": st.column_config.TextColumn("Formation", width="medium"),
                "Groupe": st.column_config.TextColumn("Groupe", width="small"),
                "Module": st.column_config.TextColumn("Module", width="large"),
                "Date": st.column_config.TextColumn("Date", width="small"),
                "Heure": st.column_config.TextColumn("Heure", width="small"),
                "Salle": st.column_config.TextColumn("Salle", width="small"),
                "Surveillant": st.column_config.TextColumn("Surveillant", width="medium"),
                "Durée": st.column_config.TextColumn("Durée", width="small"),
                "Statut": st.column_config.TextColumn("Statut", width="small"),
                "ID": None  # Cacher l'ID
            },
            hide_index=True,
            use_container_width=True
        )
        
        # Options de validation
        st.markdown("---")
        st.subheader("✅ Actions de validation")
        
        # Filtrer les examens en attente
        examens_en_attente = [e for e in examens if e['statut'] == 'EN_ATTENTE']
        
        if examens_en_attente:
            # Information sur le nombre d'examens en attente
            st.info(f"**{len(examens_en_attente)}** examen(s) en attente de validation")
            
            # Options de validation
            col1, col2 = st.columns(2)
            
            with col1:
                validation_option = st.radio(
                    "Choisir l'action:",
                    ["Valider tous les examens en attente", "Refuser tous les examens en attente"]
                )
           
            # Bouton d'exécution
            action_type = "Valider" if "Valider" in validation_option else "Refuser"
            new_status = 'CONFIRME' if "Valider" in validation_option else 'REFUSE'
            button_color = "primary" if "Valider" in validation_option else "secondary"
            
            if st.button(
                f"🚀 {action_type} tous les examens en attente",
                type=button_color,
                use_container_width=True,
                key="execute_validation"
            ):
                # Exécuter la validation
                with st.spinner(f"{action_type} en cours..."):
                    success_count = 0
                    
                    for examen in examens_en_attente:
                        if update_exam_status(examen['id'], new_status, user['id']):
                            success_count += 1
                    
                    if success_count > 0:
                        if new_status == 'CONFIRME':
                            st.success(f"✅ {success_count} examens validés !")
                        else:
                            st.success(f"❌ {success_count} examens refusés !")
                        
                        st.balloons()
                        
                        # Attendre un peu puis recharger
                        import time
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("❌ Aucun examen n'a pu être traité")
        else:
            st.success("🎉 Tous les examens sont déjà validés !")
        
        # Option pour annuler les confirmations
       
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Erreur: {str(e)}")
        
def show_statistics_section(user):
    """Section de statistiques du département"""
    st.header("📊 Statistiques du Département")
    
    conn = get_connection()
    if not conn:
        st.error("Impossible de se connecter à la base de données")
        return
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # Récupérer l'ID du département du chef
        cursor.execute("""
            SELECT departement_id FROM users 
            WHERE email = %s AND role = 'CHEF_DEPT'
        """, (user['email'],))
        
        dept_info = cursor.fetchone()
        
        if not dept_info or not dept_info['departement_id']:
            st.error("Vous n'êtes pas associé à un département")
            return
        
        dept_id = dept_info['departement_id']
        
        # Statistiques générales
        st.subheader("📈 Vue d'ensemble")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            cursor.execute("""
                SELECT COUNT(*) as total_formations
                FROM formations f
                WHERE f.departement_id = %s
            """, (dept_id,))
            total_formations = cursor.fetchone()['total_formations']
            st.metric("Formations", total_formations)
        
        with col2:
            cursor.execute("""
                SELECT COUNT(*) as total_groupes
                FROM groupes g
                JOIN formations f ON g.formation_id = f.id
                WHERE f.departement_id = %s
            """, (dept_id,))
            total_groupes = cursor.fetchone()['total_groupes']
            st.metric("Groupes", total_groupes)
        
        with col3:
            cursor.execute("""
                SELECT COUNT(DISTINCT e.id) as total_examens
                FROM examens e
                JOIN formations f ON e.formation_id = f.id
                WHERE f.departement_id = %s
            """, (dept_id,))
            total_examens = cursor.fetchone()['total_examens']
            st.metric("Examens totaux", total_examens)
        
        with col4:
            cursor.execute("""
                SELECT COUNT(DISTINCT p.id) as professeurs
                FROM professeurs p
                WHERE p.departement_id = %s
            """, (dept_id,))
            total_professeurs = cursor.fetchone()['professeurs']
            st.metric("Professeurs", total_professeurs)
        
        # Graphique des examens par statut
        st.subheader("📊 Répartition des examens par statut")
        
        cursor.execute("""
            SELECT 
                e.statut,
                COUNT(*) as nombre
            FROM examens e
            JOIN formations f ON e.formation_id = f.id
            WHERE f.departement_id = %s
            GROUP BY e.statut
            ORDER BY 
                CASE e.statut 
                    WHEN 'EN_ATTENTE' THEN 1
                    WHEN 'CONFIRME' THEN 2
                    WHEN 'REFUSE' THEN 3
                END
        """, (dept_id,))
        
        stats_status = cursor.fetchall()
        
        if stats_status:
            import pandas as pd
            
            df_status = pd.DataFrame(stats_status)
            
            # Mapper les statuts en français
            status_labels = {
                'EN_ATTENTE': 'En attente',
                'CONFIRME': 'Confirmé',
                'REFUSE': 'Refusé'
            }
            
            df_status['statut_label'] = df_status['statut'].map(status_labels)
            
            # Afficher le graphique
            st.bar_chart(df_status.set_index('statut_label')['nombre'])
            
            # Tableau détaillé
            st.write("**Détail par statut:**")
            for stat in stats_status:
                status_text = status_labels.get(stat['statut'], stat['statut'])
                percentage = (stat['nombre'] / total_examens * 100) if total_examens > 0 else 0
                st.write(f"- {status_text}: {stat['nombre']} examens ({percentage:.1f}%)")
        
        # Statistiques par formation
        st.subheader("🎓 Examens par formation")
        
        cursor.execute("""
            SELECT 
                f.nom as formation,
                COUNT(e.id) as total_examens,
                SUM(CASE WHEN e.statut = 'CONFIRME' THEN 1 ELSE 0 END) as confirmes,
                SUM(CASE WHEN e.statut = 'EN_ATTENTE' THEN 1 ELSE 0 END) as en_attente,
                SUM(CASE WHEN e.statut = 'REFUSE' THEN 1 ELSE 0 END) as refuses
            FROM formations f
            LEFT JOIN examens e ON f.id = e.formation_id
            WHERE f.departement_id = %s
            GROUP BY f.id, f.nom
            ORDER BY f.nom
        """, (dept_id,))
        
        stats_formations = cursor.fetchall()
        
        if stats_formations:
            import pandas as pd
            
            df_formations = pd.DataFrame(stats_formations)
            
            # Calculer les pourcentages
            for idx, row in df_formations.iterrows():
                total = row['total_examens']
                if total > 0:
                    df_formations.loc[idx, 'confirme_pct'] = (row['confirmes'] / total * 100)
                    df_formations.loc[idx, 'attente_pct'] = (row['en_attente'] / total * 100)
                    df_formations.loc[idx, 'refuse_pct'] = (row['refuses'] / total * 100)
            
            # Afficher un tableau interactif
            st.dataframe(
                df_formations,
                column_config={
                    "formation": "Formation",
                    "total_examens": "Total",
                    "confirmes": "✅ Confirmés",
                    "en_attente": "⏳ En attente",
                    "refuses": "❌ Refusés"
                },
                hide_index=True
            )
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        st.error(f"Erreur lors du chargement des statistiques: {str(e)}")

def update_exam_status(exam_id, new_status, user_id, commentaire=None):
    """Mettre à jour le statut d'un examen"""
    conn = get_connection()
    if not conn:
        return False
    
    try:
        cursor = conn.cursor()
        
        # Mettre à jour le statut de l'examen
        cursor.execute("""
            UPDATE examens 
            SET statut = %s, 
                last_modified = NOW(),
                modified_by = %s
            WHERE id = %s
        """, (new_status, user_id, exam_id))
        
        conn.commit()
        
        # Ajouter un message dans la session si l'examen est refusé
        if new_status == 'REFUSE':
            st.session_state['admin_alert'] = {
                'type': 'exam_refused',
                'exam_id': exam_id,
                'user_id': user_id,
                'message': f"Un examen (ID: {exam_id}) a été refusé par le chef de département. Veuillez regénérer le planning.",
            }
        
        # Enregistrer l'action dans planning_generations
        cursor.execute("""
            INSERT INTO planning_generations 
            (generated_by, generation_date, exams_scheduled, parameters)
            VALUES (%s, NOW(), 1, %s)
        """, (user_id, f"Changement statut examen {exam_id} -> {new_status}. Commentaire: {commentaire or 'Aucun'}"))
        
        conn.commit()
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Erreur lors de la mise à jour: {str(e)}")
        return False