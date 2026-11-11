# TTA


📡 CampusShare
> **Plateforme réseau P2P décentralisée pour campus universitaires** — Partage de cours, chat et visioconférence (Meet) en réseau local Wi-Fi, sans connexion Internet requise (**0 Mo de Data Internet consommé**).
---
📋 Sommaire
À propos du projet
Fonctionnalités clés
Architecture Technique
Structure du Dépôt
Protocole Réseau P2P & Sécurité
Endpoints API REST & WebSockets
Installation & Démarrage Rapide
Feuille de Route (Roadmap)
Contribution & Licence
---
🎯 À propos du projet
En environnement universitaire, l'accès à Internet est souvent limité, coûteux ou sujet à des coupures d'électricité récurrentes (délestages).
CampusShare résout ce problème en exploitant le réseau Wi-Fi local (Mesh / Wi-Fi Direct) de l'établissement. L'application permet aux étudiants et aux enseignants de :
Échanger des fichiers de cours (CM, TD, TP, corrections d'examens) à ultra-haute vitesse (jusqu'à 52 Mo/s).
Discuter en direct par canal d'Unité d'Enseignement (UE).
Lancer des visioconférences ou cours à distance (Local P2P Meets) avec partage d'écran à très faible latence (< 2 ms).
---
✨ Fonctionnalités clés
⚡ Zero Internet Data : Fonctionne à 100% sur le réseau local (LAN / Wi-Fi de l'amphi).
🛡️ Anti-Blackout Cache : Découpage des fichiers en blocs vérifiés par hachage SHA-256. En cas de coupure de courant ou de Wi-Fi, le téléchargement reprend exactement là où il s'était arrêté.
🤝 Découverte Automatique de Pairs (P2P Mesh) : Détection automatique des étudiants connectés dans l'amphithéâtre via UDP Broadcast / Zeroconf.
📹 Local P2P Calls & Screen Sharing : Visioconférences animées par les enseignants ou délégués basées sur WebRTC natif.
🔐 Badge Étudiant & Rôles : Authentification sécurisée par matricule/badge universitaire avec attribution des rôles (Faculty Host / Student Peer).
---
🏗️ Architecture Technique
```
+-------------------------------------------------------------------------------+
|                       FRONTEND CLIENT (Python Flet)                           |
|  - UI Réactive (Chat, Cours & TP, Local P2P Calls, Settings)                 |
|  - Moteur Local & Cache (Stockage chiffré par bloc SHA-256)                  |
|  - Client WebRTC (Appels P2P) & Sockets TCP Directs (Seeder / Leecher)        |
+---------------------------------------|---------------------------------------+
                                        | HTTP REST / WebSockets (LAN Wi-Fi)
                                        v
+-------------------------------------------------------------------------------+
|                       BACKEND CENTRAL (Python Django)                         |
|  - Django REST Framework : Indexation des cours & Annuaire des Nœuds          |
|  - Django Channels (WebSockets) : Signalement SDP/ICE WebRTC & Presences      |
|  - Base de données : PostgreSQL / SQLite (Stockage des métadonnées)           |
+-------------------------------------------------------------------------------+
```
---
📁 Structure du Dépôt
Le projet est organisé selon une séparation stricte entre le Backend Django (indexation et signalement) et le Frontend Flet (interface et moteur P2P).
```text
campus-share/
│
├── backend/                        # Serveur Django (API & Signalement WebRTC)
│   ├── manage.py
│   ├── config/                     # Paramètres globaux, ASGI/WSGI, routing URLs
│   │   ├── settings.py
│   │   ├── asgi.py
│   │   └── urls.py
│   ├── apps/
│   │   ├── authentication/         # Gestion des utilisateurs et badges étudiants (STU-XXXX)
│   │   ├── network_registry/       # Annuaire des nœuds actifs sur le réseau (IP/Port)
│   │   ├── repository/             # Index des fichiers (Hash SHA-256, Seeders)
│   │   ├── signaling/              # Consumer WebSocket pour la négociation WebRTC
│   │   └── chat/                   # Historique des messages par Unité d'Enseignement
│   └── requirements.txt
│
├── frontend/                       # Client Desktop/Mobile (Python Flet)
│   ├── main.py                     # Point d'entrée de l'application UI Flet
│   ├── config.py                   # IP du serveur local et ports par défaut
│   ├── core/                       # Moteurs réseau natifs & I/O
│   │   ├── p2p_socket_engine.py    # Serveur/Client TCP pour transfert de blocs
│   │   ├── storage_manager.py      # Cache local anti-blackout & validation SHA-256
│   │   ├── zeroconf_scanner.py     # Scanner de réseau local (UDP broadcast)
│   │   └── webrtc_engine.py        # Gestionnaire de flux audio/vidéo P2P
│   ├── services/                   # Connecteurs d'API Backend
│   │   ├── api_client.py           # Requêtes HTTP/REST vers Django
│   │   ├── websocket_client.py     # Signalisation WebSockets
│   │   └── auth_service.py         # Authentification et gestion des tokens JWT
│   ├── state/                      # Gestionnaires d'état réactifs
│   │   ├── app_state.py            # Statut du nœud (IP, débit, mode Anti-Lag)
│   │   └── network_state.py        # Liste des pairs et salons actifs
│   └── views/                      # Écrans de l'interface Flet
│       ├── components/             # Sidebar, Header réseau, cartes de cours
│       ├── chat_view.py            # Interface des salons de discussion
│       ├── courses_view.py         # Bibliothèque des ressources éducatives
│       ├── calls_view.py            # Visioconférence & Partage d'écran (Meet)
│       └── settings_view.py        # Configuration du nœud & allocation du cache
│
├── docker-compose.yml              # Lancement du backend local via Docker
└── README.md                       # Documentation officielle du projet
```
---
🔒 Protocole Réseau P2P & Sécurité
1. Transfert de Fichiers (Direct P2P Link)
Publication : Le fichier est découpé localement en blocs (chunks) de 1 Mo. Le hash SHA-256 du fichier global et de chaque bloc est calculé et enregistré sur l'index Django.
Découverte des Seeders : Lorsqu'un étudiant clique sur `Télécharger`, Flet demande à Django l'IP des étudiants (seeders) possédant déjà ce fichier.
Aspiration TCP Directe : Le client ouvre des sockets TCP natifs avec les seeders. Le transfert s'effectue en direct de pair à pair.
2. Visioconférence (Local P2P Meet)
Le client émetteur crée une offre SDP (Session Description Protocol).
L'offre est transmise au destinataire via le canal WebSocket Django Channels (`/ws/signaling/<room_id>/`).
Les candidats ICE sont échangés. La connexion média WebRTC s'établit en direct entre les deux appareils sans surcharger le serveur.
---
🔌 Endpoints API REST & WebSockets
REST API (Django REST Framework)
Méthode	Endpoint	Description
`POST`	`/api/v1/auth/login/`	Connexion étudiant et obtention du Token JWT
`GET`	`/api/v1/network/peers/`	Liste des nœuds pairs actifs sur le sous-réseau amphi
`GET`	`/api/v1/resources/`	Recherche et filtrage de cours (CM, TD, TP, Examens)
`POST`	`/api/v1/resources/announce/`	Déclarer la détention d'un fichier (devenir Seeder)
WebSockets
Route	Description
`ws://<server_ip>:8000/ws/chat/<ue_code>/`	Canal de discussion texte en temps réel par UE
`ws://<server_ip>:8000/ws/signaling/<room_id>/`	Canal de signalement WebRTC pour appels vidéo et partage d'écran
---
🚀 Installation & Démarrage Rapide
Prérequis
Python 3.10+ installe sur les machines
Git
Connecté au même réseau Wi-Fi local (pas besoin de connexion Internet)
1. Lancement du Backend Django
```bash
# Se déplacer dans le dossier backend
cd backend

# Créer et activer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer les dépendances
pip install -r requirements.txt

# Appliquer les migrations et lancer le serveur
python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```
2. Lancement du Client Flet (Frontend)
```bash
# Ouvrir un nouveau terminal dans le dossier frontend
cd frontend

# Créer et activer un environnement virtuel
python -m venv venv
source venv/bin/activate  # Sur Windows: venv\Scripts\activate

# Installer Flet et les dépendances réseau
pip install flet httpx zeroconf aiortc

# Lancer l'application
python main.py
```
---
🗓️ Feuille de Route (Roadmap - 1.5 Semaine)
[x] Jour 1-2 : Architecture des dossiers, schéma BDD Django et maquettage UI Flet.
[x] Jour 3-4 : Développement du registre des nœuds et scanner UDP Zeroconf.
[ ] Jour 5-7 : Moteur P2P de transfert par bloc (Sockets TCP & Anti-Blackout Cache).
[ ] Jour 8-9 : Signalisation WebSockets & Moteur d'appel WebRTC P2P (Local Meet).
[ ] Jour 10 : Tests de charge en amphi, recette globale et livraison du binaire.
---
📄 Licence & Crédits
Projet développé par Alexandre Dumas & l'Équipe Ingénierie Logicielle Groupe 9.  
Distribué sous licence MIT. Libre d'utilisation pour tous les établissements d'enseignement supérieur.