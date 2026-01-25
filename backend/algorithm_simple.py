# backend/algorithm_simple.py - VERSION CORRIGÉE AVEC SALLES DIFFÉRENTES
import mysql.connector
from mysql.connector import Error
from datetime import datetime, timedelta
import time

class SimplePlanningGenerator:
    def __init__(self, db_config=None):
        """Initialiser le générateur simplifié"""
        if db_config is None:
            self.db_config = {
                'host': 'localhost',
                'user': 'root',
                'password': '',
                'database': 'edt_exam'
            }
        else:
            self.db_config = db_config
        
        # Créneaux fixes de 1h30
        self.time_slots = [
            '08:00:00',  # 8h-9h30
            '09:30:00',  # 9h30-11h
             '10:00:00',
            '11:00:00',  # 11h-12h30
            '14:00:00',  # 14h-15h30
            '15:00:00',  # 15h30-17h
             '16:30:00',
           
        ]
    
    def get_connection(self):
        """Établir la connexion à la base de données"""
        try:
            conn = mysql.connector.connect(**self.db_config)
            return conn
        except Error as e:
            print(f"Erreur de connexion: {e}")
            return None
    
    def create_session_and_exams(self, nom_session, date_debut, date_fin, formation_ids):
        """Créer une session et générer tous les examens automatiquement PAR GROUPE"""
        conn = self.get_connection()
        if not conn:
            return {"success": False, "message": "Erreur de connexion"}
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # VÉRIFICATION DES DOUBLONS AVANT LA CRÉATION
            cursor.execute("""
                SELECT id, nom, date_debut, date_fin 
                FROM sessions_examens 
                WHERE nom = %s 
                AND (
                    (date_debut BETWEEN %s AND %s) 
                    OR (date_fin BETWEEN %s AND %s)
                    OR (%s BETWEEN date_debut AND date_fin)
                    OR (%s BETWEEN date_debut AND date_fin)
                )
            """, (nom_session, date_debut, date_fin, date_debut, date_fin, date_debut, date_fin))
            
            existing_session = cursor.fetchone()
            if existing_session:
                cursor.close()
                conn.close()
                return {
                    "success": False,
                    "message": f"❌ Impossible de créer la session. Une session '{nom_session}' existe déjà du {existing_session['date_debut']} au {existing_session['date_fin']}.",
                    "session_id": None,
                    "exams_created": 0
                }
            
            # 1. Créer la session
            cursor.execute("""
                INSERT INTO sessions_examens (nom, date_debut, date_fin, statut)
                VALUES (%s, %s, %s, 'CREATION')
            """, (nom_session, date_debut, date_fin))
            
            session_id = cursor.lastrowid
            
            # 2. Générer les examens pour chaque groupe de chaque formation
            examens_crees = 0
            
            for formation_id in formation_ids:
                # Récupérer tous les modules de cette formation
                cursor.execute("""
                    SELECT id FROM modules WHERE formation_id = %s
                """, (formation_id,))
                
                modules = cursor.fetchall()
                
                # Récupérer tous les groupes de cette formation
                cursor.execute("""
                    SELECT id, nom, effectif FROM groupes 
                    WHERE formation_id = %s
                """, (formation_id,))
                
                groupes = cursor.fetchall()
                
                # Créer un examen pour chaque module et chaque groupe
                for module in modules:
                    for groupe in groupes:
                        cursor.execute("""
                            INSERT INTO examens (
                                module_id, formation_id, session_id,
                                duree_minutes, priorite, statut,
                                groupe_id
                            ) VALUES (%s, %s, %s, 90, 2, 'EN_ATTENTE', %s)
                        """, (module['id'], formation_id, session_id, groupe['id']))
                        
                        examens_crees += 1
            
            conn.commit()
            
            # 3. Planifier automatiquement les examens (planification automatique)
            planning_results = self.planify_session(session_id)
            
            cursor.close()
            conn.close()
            
            return {
                "success": True,
                "message": f"Session créée avec {examens_crees} examens (en attente de validation)",
                "session_id": session_id,
                "exams_created": examens_crees,
                "planning_results": planning_results
            }
            
        except Error as e:
            print(f"Erreur: {e}")
            if conn:
                try:
                    conn.rollback()
                except:
                    pass
            return {"success": False, "message": str(e)}
    
    def planify_session(self, session_id):
        """
        Planifier automatiquement tous les examens d'une session
        NOUVELLE LOGIQUE: Tous les groupes d'une même formation passent
        le même module en même temps (même jour, même heure) dans des salles différentes
        """
        start_time = time.time()
        
        conn = self.get_connection()
        if not conn:
            return {"success": False, "message": "Erreur de connexion"}
        
        try:
            cursor = conn.cursor(dictionary=True)
            
            # 1. Récupérer les infos de la session
            cursor.execute("SELECT * FROM sessions_examens WHERE id = %s", (session_id,))
            session = cursor.fetchone()
            
            if not session:
                return {"success": False, "message": "Session non trouvée"}
            
            # 2. Récupérer tous les examens EN_ATTENTE
            cursor.execute("""
                SELECT e.*, 
                       e.groupe_id,
                       g.nom as groupe_nom,
                       g.effectif as groupe_effectif,
                       f.departement_id,
                       m.nom as module_nom,
                       f.nom as formation_nom,
                       m.id as module_id
                FROM examens e
                JOIN modules m ON e.module_id = m.id
                JOIN formations f ON e.formation_id = f.id
                JOIN groupes g ON e.groupe_id = g.id
                WHERE e.session_id = %s
                ORDER BY f.id, m.id, g.id
            """, (session_id,))
            
            exams = cursor.fetchall()
            
            if not exams:
                cursor.close()
                conn.close()
                return {
                    "success": True,
                    "message": "Aucun examen à planifier",
                    "exams_scheduled": 0,
                    "execution_time": 0,
                    "details": []
                }
            
            # 3. Générer les dates de la session (jours ouvrables)
            current_date = session['date_debut']
            end_date = session['date_fin']
            session_dates = []
            
            while current_date <= end_date:
                if current_date.weekday() < 5:  # Exclure weekends
                    session_dates.append(current_date)
                current_date += timedelta(days=1)
            
            # 4. Récupérer toutes les salles
            cursor.execute("SELECT id, nom, capacite FROM salles ORDER BY capacite DESC")
            salles = cursor.fetchall()
            
            # 5. Récupérer tous les professeurs
            cursor.execute("""
                SELECT p.id, p.departement_id, p.nb_max_surveillances_jour, u.email,
                       COUNT(s.id) as surveillances_actuelles
                FROM professeurs p
                JOIN users u ON p.user_id = u.id
                LEFT JOIN surveillances s ON p.id = s.prof_id
                GROUP BY p.id
                ORDER BY surveillances_actuelles ASC
            """)
            professeurs = cursor.fetchall()
            
            # 6. Organiser les examens par formation et module
            # Structure: {formation_id: {module_id: [examens par groupe]}}
            formation_module_exams = {}
            
            for exam in exams:
                formation_id = exam['formation_id']
                module_id = exam['module_id']
                
                if formation_id not in formation_module_exams:
                    formation_module_exams[formation_id] = {}
                
                if module_id not in formation_module_exams[formation_id]:
                    formation_module_exams[formation_id][module_id] = []
                
                formation_module_exams[formation_id][module_id].append(exam)
            
            # 7. Planifier les examens
            exams_scheduled = 0
            details = []
            
            # Dictionnaires pour suivre les contraintes
            contraintes = {
                'salles_occupees': {},        # {(date, heure): [salle_ids]}
                'professeurs_occupes': {},    # {(date, prof_id): count}
                'groupes_jour': {},           # {(date, groupe_id): bool}
                'formation_module_creneau': {} # {(date, heure, formation_id, module_id): bool}
            }
            
            # Pour chaque formation
            for formation_id, modules_dict in formation_module_exams.items():
                # Pour chaque module de cette formation
                for module_id, module_exams in modules_dict.items():
                    scheduled = False
                    
                    # Essayer chaque date dans l'ordre
                    for date in session_dates:
                        if scheduled:
                            break
                        
                        date_str = str(date)
                        
                        # Vérifier si un groupe a déjà un examen ce jour-là
                        groupes_disponibles = []
                        groupes_indisponibles = []
                        
                        for exam in module_exams:
                            groupe_key = (date_str, exam['groupe_id'])
                            if contraintes['groupes_jour'].get(groupe_key, False):
                                groupes_indisponibles.append(exam['groupe_nom'])
                            else:
                                groupes_disponibles.append(exam)
                        
                        # Si aucun groupe n'est disponible ce jour, on passe au jour suivant
                        if not groupes_disponibles:
                            continue
                        
                        # Si certains groupes ne sont pas disponibles, on continue quand même avec ceux qui le sont
                        if groupes_indisponibles:
                            print(f"Note: Groupes {', '.join(groupes_indisponibles)} déjà occupés le {date}")
                        
                        # Essayer chaque créneau horaire
                        for time_slot in self.time_slots:
                            if scheduled:
                                break
                            
                            # Vérifier si ce module de cette formation est déjà planifié à ce créneau
                            module_creneau_key = (date_str, time_slot, formation_id, module_id)
                            if contraintes['formation_module_creneau'].get(module_creneau_key, False):
                                continue
                            
                            # Vérifier s'il y a assez de salles disponibles POUR TOUS LES GROUPES
                            # Chercher des salles UNIQUES pour chaque groupe
                            salles_disponibles = [s for s in salles]
                            salles_trouvees = []  # Liste de tuples (salle, exam)
                            professeurs_trouves = []  # Liste de tuples (prof, exam)
                            
                            # Pour chaque groupe, trouver une salle et un professeur
                            tous_trouves = True
                            
                            for exam in groupes_disponibles:
                                # Chercher une salle disponible pour CE groupe
                                salle_trouvee = None
                                
                                for salle in salles_disponibles:
                                    # Vérifier si la salle est déjà occupée à ce créneau
                                    salle_key = (date_str, time_slot)
                                    salles_occupees = contraintes['salles_occupees'].get(salle_key, [])
                                    
                                    if salle['id'] in salles_occupees:
                                        continue  # Salle déjà occupée ce créneau
                                    
                                    # Vérifier capacité
                                    if salle['capacite'] < exam['groupe_effectif']:
                                        continue  # Salle trop petite
                                    
                                    salle_trouvee = salle
                                    break
                                
                                if not salle_trouvee:
                                    tous_trouves = False
                                    break
                                
                                # Chercher un professeur disponible pour CE groupe
                                prof_trouve = None
                                
                                for prof in professeurs:
                                    # Vérifier si ce professeur est déjà utilisé pour un autre groupe de ce module
                                    if any(p[0]['id'] == prof['id'] for p in professeurs_trouves):
                                        continue  # Professeur déjà utilisé pour un autre groupe
                                    
                                    # Vérifier département
                                    if prof['departement_id'] != exam['departement_id']:
                                        continue
                                    
                                    # Vérifier indisponibilités
                                    cursor.execute("""
                                        SELECT COUNT(*) as count
                                        FROM indisponibilites_professeurs
                                        WHERE prof_id = %s 
                                        AND %s BETWEEN date_debut AND date_fin
                                    """, (prof['id'], date))
                                    
                                    if cursor.fetchone()['count'] > 0:
                                        continue
                                    
                                    # Vérifier le nombre de surveillances du jour (max 3)
                                    prof_key = (date_str, prof['id'])
                                    nb_surveillances = contraintes['professeurs_occupes'].get(prof_key, 0)
                                    if nb_surveillances >= prof['nb_max_surveillances_jour']:
                                        continue
                                    
                                    # Vérifier si le professeur n'a pas déjà un examen à cette heure
                                    cursor.execute("""
                                        SELECT COUNT(*) as count
                                        FROM surveillances s
                                        JOIN examens e ON s.examen_id = e.id
                                        WHERE s.prof_id = %s 
                                        AND s.date_surveillance = %s
                                        AND s.heure_debut = %s
                                    """, (prof['id'], date, time_slot))
                                    
                                    if cursor.fetchone()['count'] > 0:
                                        continue
                                    
                                    prof_trouve = prof
                                    break
                                
                                if not prof_trouve:
                                    tous_trouves = False
                                    break
                                
                                # Ajouter à nos listes
                                salles_trouvees.append((salle_trouvee, exam))
                                professeurs_trouves.append((prof_trouve, exam))
                                
                                # Retirer la salle des disponibles pour éviter de la réutiliser
                                salles_disponibles = [s for s in salles_disponibles if s['id'] != salle_trouvee['id']]
                            
                            # Si on a trouvé des salles et professeurs pour tous les groupes
                            if tous_trouves and len(salles_trouvees) == len(groupes_disponibles):
                                # Maintenant planifier tous les examens de ce module
                                for i in range(len(groupes_disponibles)):
                                    salle_trouvee, exam = salles_trouvees[i]
                                    prof_trouve, _ = professeurs_trouves[i]
                                    
                                    # Planifier l'examen
                                    cursor.execute("""
                                        UPDATE examens 
                                        SET date_examen = %s,
                                            heure_debut = %s,
                                            salle_id = %s,
                                            duree_minutes = 90,
                                            statut = 'EN_ATTENTE'
                                        WHERE id = %s
                                    """, (date, time_slot, salle_trouvee['id'], exam['id']))
                                    
                                    # Ajouter la surveillance
                                    cursor.execute("""
                                        INSERT INTO surveillances (examen_id, salle_id, prof_id, date_surveillance, heure_debut)
                                        VALUES (%s, %s, %s, %s, %s)
                                    """, (exam['id'], salle_trouvee['id'], prof_trouve['id'], date, time_slot))
                                    
                                    # Mettre à jour les contraintes
                                    salle_key = (date_str, time_slot)
                                    if salle_key not in contraintes['salles_occupees']:
                                        contraintes['salles_occupees'][salle_key] = []
                                    contraintes['salles_occupees'][salle_key].append(salle_trouvee['id'])
                                    
                                    prof_key = (date_str, prof_trouve['id'])
                                    contraintes['professeurs_occupes'][prof_key] = contraintes['professeurs_occupes'].get(prof_key, 0) + 1
                                    
                                    groupe_key = (date_str, exam['groupe_id'])
                                    contraintes['groupes_jour'][groupe_key] = True
                                    
                                    exams_scheduled += 1
                                    details.append({
                                        'examen_id': exam['id'],
                                        'module': exam['module_nom'],
                                        'formation': exam['formation_nom'],
                                        'groupe': exam['groupe_nom'],
                                        'effectif': exam['groupe_effectif'],
                                        'date': str(date),
                                        'heure': time_slot[:5],
                                        'salle': salle_trouvee['nom'],
                                        'professeur': prof_trouve['email'],
                                        'capacite_salle': salle_trouvee['capacite'],
                                        'statut': 'EN_ATTENTE'
                                    })
                                
                                # Marquer ce module comme planifié à ce créneau
                                module_creneau_key = (date_str, time_slot, formation_id, module_id)
                                contraintes['formation_module_creneau'][module_creneau_key] = True
                                
                                scheduled = True
                                print(f"✓ Planifié: {exam['formation_nom']} - {exam['module_nom']} à {time_slot} le {date} dans {len(groupes_disponibles)} salles différentes")
                                break  # Sortir de la boucle des créneaux
                    
                    if not scheduled:
                        # Marquer les examens non planifiés
                        for exam in module_exams:
                            details.append({
                                'examen_id': exam['id'],
                                'module': exam['module_nom'],
                                'formation': exam['formation_nom'],
                                'groupe': exam['groupe_nom'],
                                'status': f'NON PLANIFIÉ - Pas de créneau disponible avec assez de salles/professeurs'
                            })
            
            # 8. Mettre à jour le statut de la session
            cursor.execute("""
                UPDATE sessions_examens 
                SET statut = 'PLANIFICATION'
                WHERE id = %s
            """, (session_id,))
            
            conn.commit()
            
            end_time = time.time()
            
            return {
                "success": True,
                "message": f"{exams_scheduled}/{len(exams)} examens planifiés (en attente de validation)",
                "exams_scheduled": exams_scheduled,
                "execution_time": round(end_time - start_time, 2),
                "details": details
            }
            
        except Error as e:
            print(f"Erreur de planification: {e}")
            import traceback
            print(f"Traceback: {traceback.format_exc()}")
            return {"success": False, "message": str(e)}
        finally:
            if conn:
                cursor.close()
                conn.close()
    
    def detecter_conflits(self, session_id):
        """Détecter les conflits dans une session"""
        conn = self.get_connection()
        if not conn:
            return {"success": False, "message": "Erreur de connexion"}
        
        try:
            cursor = conn.cursor(dictionary=True)
            conflits = []
            
            # 1. Conflits de professeurs (même prof à deux endroits en même temps)
            cursor.execute("""
                SELECT s1.prof_id, s1.date_surveillance, s1.heure_debut,
                       e1.id as examen1_id, e2.id as examen2_id,
                       p.email as prof_email,
                       m1.nom as module1_nom, m2.nom as module2_nom,
                       f1.nom as formation1_nom, f2.nom as formation2_nom
                FROM surveillances s1
                JOIN surveillances s2 ON s1.prof_id = s2.prof_id 
                    AND s1.date_surveillance = s2.date_surveillance 
                    AND s1.heure_debut = s2.heure_debut 
                    AND s1.id < s2.id
                JOIN examens e1 ON s1.examen_id = e1.id
                JOIN examens e2 ON s2.examen_id = e2.id
                JOIN professeurs p ON s1.prof_id = p.id
                JOIN modules m1 ON e1.module_id = m1.id
                JOIN modules m2 ON e2.module_id = m2.id
                JOIN formations f1 ON e1.formation_id = f1.id
                JOIN formations f2 ON e2.formation_id = f2.id
                WHERE e1.session_id = %s OR e2.session_id = %s
            """, (session_id, session_id))
            
            for conflit in cursor.fetchall():
                conflits.append({
                    'type': 'PROFESSEUR',
                    'description': f"Le professeur {conflit['prof_email']} est assigné à deux examens en même temps ({conflit['formation1_nom']} - {conflit['module1_nom']} et {conflit['formation2_nom']} - {conflit['module2_nom']})",
                    'details': conflit
                })
            
            # 2. Conflits de salles (même salle à deux examens en même temps)
            cursor.execute("""
                SELECT e1.salle_id, e1.date_examen, e1.heure_debut,
                       e1.id as examen1_id, e2.id as examen2_id,
                       s.nom as salle_nom,
                       m1.nom as module1_nom, m2.nom as module2_nom,
                       f1.nom as formation1_nom, f2.nom as formation2_nom,
                       g1.nom as groupe1_nom, g2.nom as groupe2_nom
                FROM examens e1
                JOIN examens e2 ON e1.salle_id = e2.salle_id 
                    AND e1.date_examen = e2.date_examen 
                    AND e1.heure_debut = e2.heure_debut 
                    AND e1.id < e2.id
                JOIN salles s ON e1.salle_id = s.id
                JOIN modules m1 ON e1.module_id = m1.id
                JOIN modules m2 ON e2.module_id = m2.id
                JOIN formations f1 ON e1.formation_id = f1.id
                JOIN formations f2 ON e2.formation_id = f2.id
                JOIN groupes g1 ON e1.groupe_id = g1.id
                JOIN groupes g2 ON e2.groupe_id = g2.id
                WHERE (e1.session_id = %s OR e2.session_id = %s)
                    AND e1.salle_id IS NOT NULL
            """, (session_id, session_id))
            
            for conflit in cursor.fetchall():
                conflits.append({
                    'type': 'SALLE',
                    'description': f"La salle {conflit['salle_nom']} est utilisée pour deux examens en même temps: {conflit['formation1_nom']} ({conflit['groupe1_nom']}) - {conflit['module1_nom']} et {conflit['formation2_nom']} ({conflit['groupe2_nom']}) - {conflit['module2_nom']}",
                    'details': conflit
                })
            
            # 3. Conflits d'étudiants (même groupe à deux examens en même temps)
            cursor.execute("""
                SELECT e1.groupe_id, e1.date_examen, e1.heure_debut,
                       e1.id as examen1_id, e2.id as examen2_id,
                       g.nom as groupe_nom,
                       m1.nom as module1_nom, m2.nom as module2_nom,
                       f1.nom as formation1_nom
                FROM examens e1
                JOIN examens e2 ON e1.groupe_id = e2.groupe_id 
                    AND e1.date_examen = e2.date_examen 
                    AND e1.heure_debut = e2.heure_debut 
                    AND e1.id < e2.id
                JOIN groupes g ON e1.groupe_id = g.id
                JOIN modules m1 ON e1.module_id = m1.id
                JOIN modules m2 ON e2.module_id = m2.id
                JOIN formations f1 ON e1.formation_id = f1.id
                WHERE (e1.session_id = %s OR e2.session_id = %s)
                    AND e1.groupe_id IS NOT NULL
            """, (session_id, session_id))
            
            for conflit in cursor.fetchall():
                conflits.append({
                    'type': 'ETUDIANT',
                    'description': f"Le groupe {conflit['groupe_nom']} ({conflit['formation1_nom']}) a deux examens en même temps ({conflit['module1_nom']} et {conflit['module2_nom']})",
                    'details': conflit
                })
            
            # 4. Vérifier si un professeur a plus de 3 surveillances par jour
            cursor.execute("""
                SELECT s.prof_id, s.date_surveillance,
                       COUNT(*) as nb_surveillances,
                       p.nb_max_surveillances_jour,
                       u.email as prof_email
                FROM surveillances s
                JOIN professeurs p ON s.prof_id = p.id
                JOIN users u ON p.user_id = u.id
                JOIN examens e ON s.examen_id = e.id
                WHERE e.session_id = %s
                GROUP BY s.prof_id, s.date_surveillance
                HAVING COUNT(*) > p.nb_max_surveillances_jour
            """, (session_id,))
            
            for conflit in cursor.fetchall():
                conflits.append({
                    'type': 'LIMITE_PROFESSEUR',
                    'description': f"Le professeur {conflit['prof_email']} a {conflit['nb_surveillances']} surveillances le {conflit['date_surveillance']} (limite: {conflit['nb_max_surveillances_jour']})",
                    'details': conflit
                })
            
            # 5. Vérifier si des groupes d'une même formation ont la même salle pour le même module
            cursor.execute("""
                SELECT e1.formation_id, e1.module_id, e1.date_examen, e1.heure_debut,
                       e1.salle_id, e2.salle_id, e1.groupe_id as groupe1_id, e2.groupe_id as groupe2_id,
                       g1.nom as groupe1_nom, g2.nom as groupe2_nom,
                       f.nom as formation_nom, m.nom as module_nom, s.nom as salle_nom
                FROM examens e1
                JOIN examens e2 ON e1.formation_id = e2.formation_id 
                    AND e1.module_id = e2.module_id 
                    AND e1.date_examen = e2.date_examen 
                    AND e1.heure_debut = e2.heure_debut 
                    AND e1.id < e2.id
                    AND e1.salle_id = e2.salle_id
                JOIN formations f ON e1.formation_id = f.id
                JOIN modules m ON e1.module_id = m.id
                JOIN groupes g1 ON e1.groupe_id = g1.id
                JOIN groupes g2 ON e2.groupe_id = g2.id
                JOIN salles s ON e1.salle_id = s.id
                WHERE e1.session_id = %s
            """, (session_id,))
            
            for conflit in cursor.fetchall():
                conflits.append({
                    'type': 'SALLE_DUPLIQUEE',
                    'description': f"Deux groupes ({conflit['groupe1_nom']} et {conflit['groupe2_nom']}) de la formation {conflit['formation_nom']} ont le même module ({conflit['module_nom']}) dans la même salle ({conflit['salle_nom']}) en même temps",
                    'details': conflit
                })
            
            # Enregistrer les conflits dans la base
            for conflit in conflits:
                cursor.execute("""
                    INSERT INTO conflits_examens 
                    (examen1_id, examen2_id, type_conflit, description)
                    VALUES (%s, %s, %s, %s)
                """, (
                    conflit['details'].get('examen1_id', 0),
                    conflit['details'].get('examen2_id', 0),
                    conflit['type'],
                    conflit['description']
                ))
            
            conn.commit()
            
            return {
                "success": True,
                "message": f"{len(conflits)} conflits détectés",
                "conflits": conflits
            }
            
        except Error as e:
            print(f"Erreur détection conflits: {e}")
            return {"success": False, "message": str(e)}
        finally:
            if conn:
                cursor.close()
                conn.close()

def regenerate_session_completely(session_id):
    """
    Regénérer complètement une session : efface TOUT et refait un planning
    Version corrigée sans problème de self
    """
    start_time = time.time()
    
    generator = SimplePlanningGenerator()
    conn = generator.get_connection()
    
    if not conn:
        return {"success": False, "message": "Erreur de connexion"}
    
    try:
        cursor = conn.cursor(dictionary=True)
        
        # 1. Vérifier si la session existe
        cursor.execute("SELECT * FROM sessions_examens WHERE id = %s", (session_id,))
        session = cursor.fetchone()
        
        if not session:
            cursor.close()
            conn.close()
            return {"success": False, "message": "Session non trouvée"}
        
        # 2. SUPPRIMER TOUTES les surveillances existantes pour cette session
        cursor.execute("""
            DELETE FROM surveillances 
            WHERE examen_id IN (
                SELECT id FROM examens WHERE session_id = %s
            )
        """, (session_id,))
        
        # 3. RÉINITIALISER TOUS les examens de la session (tous statuts)
        cursor.execute("""
            UPDATE examens 
            SET date_examen = NULL,
                heure_debut = NULL,
                salle_id = NULL,
                statut = 'EN_ATTENTE',
                last_modified = NOW()
            WHERE session_id = %s
        """, (session_id,))
        
        # 4. SUPPRIMER les conflits existants
        cursor.execute("""
            DELETE FROM conflits_examens 
            WHERE examen1_id IN (
                SELECT id FROM examens WHERE session_id = %s
            ) OR examen2_id IN (
                SELECT id FROM examens WHERE session_id = %s
            )
        """, (session_id, session_id))
        
        conn.commit()
        
        # 5. Planifier à nouveau COMPLÈTEMENT
        planning_result = generator.planify_session(session_id)
        
        cursor.close()
        conn.close()
        
        end_time = time.time()
        
        return {
            "success": planning_result.get("success", False),
            "message": f"✅ Session complètement regénérée ! {planning_result.get('message', '')}",
            "execution_time": round(end_time - start_time, 2),
            "details": planning_result.get("details", []),
            "exams_scheduled": planning_result.get("exams_scheduled", 0),
            "original_message": planning_result.get("message", "")
        }
        
    except Error as e:
        print(f"Erreur de regénération complète: {e}")
        import traceback
        traceback.print_exc()
        return {"success": False, "message": f"❌ Erreur lors de la regénération: {str(e)}"}
    finally:
        if conn:
            try:
                cursor.close()
                conn.close()
            except:
                pass
# Fonctions d'interface
def create_session_and_generate_exams(nom_session, date_debut, date_fin, formation_ids):
    """Créer une session et générer les examens"""
    generator = SimplePlanningGenerator()
    return generator.create_session_and_exams(nom_session, date_debut, date_fin, formation_ids)

def planify_session_exams(session_id):
    """Planifier les examens d'une session existante"""
    generator = SimplePlanningGenerator()
    return generator.planify_session(session_id)

def detect_conflits_for_session(session_id):
    """Détecter les conflits pour une session"""
    generator = SimplePlanningGenerator()
    return generator.detecter_conflits(session_id)

# AJOUTER CETTE LIGNE juste après la fonction detect_conflits_for_session :
def regenerate_session_completely_interface(session_id):
    """Interface pour la regénération complète d'une session"""
    return regenerate_session_completely(session_id)
# Test rapide
if __name__ == "__main__":
    # Testez la planification
    test_result = create_session_and_generate_exams(
        "Test Session Salles Différentes",
        datetime.now().date() + timedelta(days=7),
        datetime.now().date() + timedelta(days=14),
        [1, 2, 3, 4, 5]  # Toutes les formations
    )
    print("Résultat du test:", test_result)