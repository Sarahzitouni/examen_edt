# frontend/app.py - Version corrigée
import streamlit as st
import sys
import os

port = int(os.environ.get("PORT", 8501))
# Ajouter le chemin du projet au PYTHONPATH
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Configuration
st.set_page_config(
    page_title="EDT Exam Platform",
    page_icon="📚",
    layout="wide"
)

# Imports relatifs
try:
    from backend.database import verify_user
    DB_AVAILABLE = True
except ImportError as e:
    DB_AVAILABLE = False
    st.warning(f"Impossible d'importer la base de données: {e}")

def login_page():
    """Page de connexion"""
    st.title(" Connexion - Plateforme EDT Examens")
    
    col1, col2, col3 = st.columns([1, 3, 1])
    
    with col2:
        with st.form("login_form"):
            email = st.text_input("📧 Email", value="ali@mail.com")
            password = st.text_input(" Mot de passe", type="password", value="1234")
            
            if st.form_submit_button(" Se connecter"):
                if DB_AVAILABLE:
                    user = verify_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Identifiants incorrects")
                else:
                    # Mode démo sans base de données
                    st.session_state.user = {
                        'id': 1,
                        'email': email,
                        'role': 'ADMIN_EXAM' if 'admin' in email else 'ETUDIANT',
                        'is_active': 1
                    }
                    st.rerun()

def main():
    """Application principale"""
    if "user" not in st.session_state:
        login_page()
    else:
        user = st.session_state.user
        role = user.get('role', 'ETUDIANT')
        
        # Dashboard selon rôle
        try:
            if role == "ETUDIANT":
                from frontend.dashboard_student import show_student_dashboard
                show_student_dashboard()
            elif role == "PROF":
                from frontend.dashboard_professor import show_professor_dashboard
                show_professor_dashboard()
            elif role == "ADMIN_EXAM":
                from frontend.dashboard_admin import show_dashboard
                show_dashboard()
            elif role == "CHEF_DEPT":
                from frontend.dashboard_chef import show_chef_dashboard
                show_chef_dashboard()
            
            else:
                st.error(f"Rôle '{role}' non pris en charge")
        except ImportError as e:
            st.error(f"Impossible de charger le dashboard: {e}")
            st.info("Mode démo - Interface de base")
            st.write(f"Connecté en tant que: {role}")
            if st.button("Déconnexion"):
                del st.session_state.user
                st.rerun()

if __name__ == "__main__":
    main()
