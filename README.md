# CampusShare

**Plateforme réseau P2P décentralisée pour campus universitaires.**

Partage de cours, chat et visioconférence (Meet) sur le Wi-Fi local, sans connexion Internet — **0 Mo de data consommé**.

| | |
| --- | --- |
| **Réseau** | LAN / Wi-Fi · Mesh · Wi-Fi Direct |
| **Client** | Python · Flet |
| **Serveur** | Django · Django REST · Channels |
| **Média** | WebRTC · TCP direct · SHA-256 |
| **Licence** | MIT |

---

## Sommaire

- [À propos](#à-propos)
- [Fonctionnalités](#fonctionnalités)
- [Architecture](#architecture)
- [Structure du dépôt](#structure-du-dépôt)
- [Protocole P2P et sécurité](#protocole-p2p-et-sécurité)
- [API REST et WebSockets](#api-rest-et-websockets)
- [Installation](#installation)
- [Feuille de route](#feuille-de-route)
- [Licence et crédits](#licence-et-crédits)

---

## À propos

En environnement universitaire, l'accès à Internet est souvent limité, coûteux ou coupé par des délestages.

CampusShare s'appuie sur le Wi-Fi local de l'établissement (mesh / Wi-Fi Direct). Étudiants et enseignants peuvent :

- échanger des fichiers de cours (CM, TD, TP, corrections) jusqu'à **52 Mo/s** ;
- discuter en direct par unité d'enseignement (UE) ;
- lancer des visioconférences locales (Local P2P Meet) avec partage d'écran, latence **inférieure à 2 ms**.

---

## Fonctionnalités

| | Fonction | Détail |
| --- | --- | --- |
| | **Zéro data Internet** | Fonctionne entièrement sur le LAN / Wi-Fi de l'amphi. |
| | **Cache anti-coupure** | Fichiers découpés en blocs vérifiés par SHA-256. Après une coupure de courant ou de Wi-Fi, le téléchargement reprend au dernier bloc reçu. |
| | **Découverte des pairs** | Détection automatique des machines de l'amphithéâtre (UDP broadcast / Zeroconf). |
| | **Appels et partage d'écran** | Visioconférences animées par les enseignants ou les délégués, via WebRTC natif. |
| | **Badge et rôles** | Connexion par matricule universitaire. Rôles `Faculty Host` et `Student Peer`. |

---

## Architecture

```text
+-------------------------------------------------------------------------------+
|                       FRONTEND CLIENT (Python Flet)                           |
|  - UI réactive (Chat, Cours & TP, Local P2P Calls, Settings)                  |
|  - Moteur local et cache (stockage chiffré par bloc SHA-256)                  |
|  - Client WebRTC (appels P2P) et sockets TCP directs (seeder / leecher)       |
+---------------------------------------|---------------------------------------+
                                        | HTTP REST / WebSockets (LAN Wi-Fi)
                                        v
+-------------------------------------------------------------------------------+
|                       BACKEND CENTRAL (Python Django)                         |
|  - Django REST Framework : index des cours et annuaire des nœuds              |
|  - Django Channels (WebSockets) : signalement SDP/ICE WebRTC et présences     |
|  - Base de données : PostgreSQL / SQLite (métadonnées uniquement)             |
+-------------------------------------------------------------------------------+
```

Le backend indexe et signale. Les fichiers et les flux média passent **directement d'un appareil à l'autre**.

---

## Structure du dépôt

Séparation stricte : Django pour l'index et le signalement, Flet pour l'interface et le moteur P2P.

```text
campus-share/
│
├── backend/                        # Serveur Django (API et signalement WebRTC)
│   ├── manage.py
│   ├── config/                     # Paramètres, ASGI/WSGI, routage
│   │   ├── settings.py
│   │   ├── asgi.py
│   │   └── urls.py
│   ├── apps/
│   │   ├── authentication/         # Utilisateurs et badges (STU-XXXX)
│   │   ├── network_registry/       # Annuaire des nœuds actifs (IP / port)
│   │   ├── repository/             # Index des fichiers (hash SHA-256, seeders)
│   │   ├── signaling/              # Consumer WebSocket (négociation WebRTC)
│   │   └── chat/                   # Historique des messages par UE
│   └── requirements.txt
│
├── frontend/                       # Client desktop / mobile (Python Flet)
│   ├── main.py                     # Point d'entrée
│   ├── config.py                   # IP du serveur local et ports
│   ├── core/                       # Moteurs réseau et I/O
│   │   ├── p2p_socket_engine.py    # TCP : transfert de blocs
│   │   ├── storage_manager.py      # Cache anti-coupure et SHA-256
│   │   ├── zeroconf_scanner.py     # Découverte locale (UDP)
│   │   └── webrtc_engine.py        # Flux audio / vidéo P2P
│   ├── services/                   # Clients du backend
│   │   ├── api_client.py           # HTTP / REST
│   │   ├── websocket_client.py     # Signalisation WebSocket
│   │   └── auth_service.py         # JWT
│   ├── state/
│   │   ├── app_state.py            # IP, débit, mode anti-lag
│   │   └── network_state.py        # Pairs et salons actifs
│   └── views/
│       ├── components/             # Sidebar, en-tête réseau, cartes de cours
│       ├── chat_view.py
│       ├── courses_view.py
│       ├── calls_view.py           # Visioconférence et partage d'écran
│       └── settings_view.py
│
├── docker-compose.yml
└── README.md
```

---

## Protocole P2P et sécurité

### 1. Transfert de fichiers

1. **Publication.** Le fichier est découpé en blocs de 1 Mo. Le SHA-256 du fichier et de chaque bloc est enregistré dans l'index Django.
2. **Découverte des seeders.** Au clic sur Télécharger, Flet demande à Django les IP des étudiants qui possèdent déjà le fichier.
3. **Transfert TCP direct.** Le client ouvre des sockets TCP vers ces seeders. Les octets ne transitent pas par le serveur.

### 2. Visioconférence (Local P2P Meet)

1. L'émetteur crée une offre SDP (Session Description Protocol).
2. L'offre passe par le canal WebSocket Django Channels : `/ws/signaling/<room_id>/`.
3. Les candidats ICE sont échangés. Le flux WebRTC s'établit ensuite **en direct** entre les deux appareils.

---

## API REST et WebSockets

### REST (Django REST Framework)

| Méthode | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/login/` | Connexion et obtention du token JWT |
| `GET` | `/api/v1/network/peers/` | Nœuds actifs sur le sous-réseau de l'amphi |
| `GET` | `/api/v1/resources/` | Recherche de cours (CM, TD, TP, examens) |
| `POST` | `/api/v1/resources/announce/` | Déclarer qu'on possède un fichier (devenir seeder) |

### WebSockets

| Route | Description |
| --- | --- |
| `ws://<server_ip>:8000/ws/chat/<ue_code>/` | Discussion texte en temps réel, par UE |
| `ws://<server_ip>:8000/ws/signaling/<room_id>/` | Signalement WebRTC (vidéo et partage d'écran) |

---

## Installation

### Prérequis

- Python 3.10 ou plus récent
- Git
- Toutes les machines sur le **même Wi-Fi local** (Internet non requis)

### 1. Backend Django

```bash
cd backend

python -m venv .venv
# Windows PowerShell : .\.venv\Scripts\Activate.ps1
# Linux / macOS      : source .venv/bin/activate

python -m pip install -r requirements.txt

python manage.py migrate
python manage.py test
python manage.py runserver 0.0.0.0:8000
```

Le backend démarre avec SQLite et le modèle utilisateur CampusShare (étudiant,
enseignant, administrateur). Le secret de développement ne doit jamais être
utilisé en production : définir `DJANGO_SECRET_KEY` et `DJANGO_DEBUG=false`
dans l'environnement de déploiement. Le serveur écoute sur toutes les
interfaces du LAN, port **8000**.

### API d'authentification

Toutes les routes sont préfixées par `/api/v1/auth/`. L'inscription publique
crée un compte étudiant; les rôles enseignant et administrateur doivent être
attribués par une personne autorisée.

| Méthode | Route | Accès | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/auth/register/` | Public | Créer un compte étudiant (`username`, `email`, `password`). |
| `POST` | `/api/v1/auth/login/` | Public | Obtenir les jetons JWT (`username`, `password`). |
| `POST` | `/api/v1/auth/refresh/` | Public | Renouveler le jeton d'accès (`refresh`). |
| `GET` | `/api/v1/auth/me/` | JWT requis | Consulter son profil avec `Authorization: Bearer <access>`. |

### API du catalogue

Toutes les routes requièrent un JWT. Les ressources sont indexées par le
backend; le contenu des fichiers n'y est pas téléversé. La publication est
réservée aux enseignants et administrateurs. Les étudiants peuvent consulter
les ressources publiées et rechercher avec `course_code`, `category` ou `q`.
Le manifeste contient les empreintes SHA-256 des blocs en hexadécimal minuscule;
l'empreinte racine est le SHA-256 de la concaténation de leurs octets décodés.

| Méthode | Route | Description |
| --- | --- | --- |
| `GET` | `/api/v1/repository/resources/` | Catalogue paginé et recherche. |
| `POST` | `/api/v1/repository/resources/` | Publier les métadonnées et le manifeste SHA-256. |
| `GET` | `/api/v1/repository/resources/{id}/` | Détail d'une ressource publiée. |
| `PATCH` | `/api/v1/repository/resources/{id}/` | Modifier sa ressource (enseignant propriétaire) ou une ressource (administrateur). |
| `DELETE` | `/api/v1/repository/resources/{id}/` | Retirer sa ressource ou une ressource (administrateur). |
| `GET` | `/api/v1/repository/resources/{id}/manifest/` | Récupérer les tailles de blocs et empreintes. |

### API du registre réseau

Toutes les routes requièrent un JWT. Un appareil s'enregistre avec une clé
publique hexadécimale, une adresse IP privée et un port TCP. Le délai
d'expiration du heartbeat est de 90 secondes par défaut et peut être réglé avec
`PEER_HEARTBEAT_TIMEOUT_SECONDS`. En production, exécuter périodiquement
`python manage.py prune_stale_nodes` pour marquer hors ligne les nœuds expirés.

| Méthode | Route | Accès | Description |
| --- | --- | --- | --- |
| `POST` | `/api/v1/network/nodes/` | JWT requis | Enregistrer un appareil pour le compte connecté. |
| `GET` | `/api/v1/network/nodes/` | JWT requis | Lister ses propres appareils enregistrés. |
| `POST` | `/api/v1/network/nodes/{id}/heartbeat/` | Propriétaire | Actualiser la présence de son appareil. |
| `DELETE` | `/api/v1/network/nodes/{id}/` | Propriétaire | Désenregistrer son appareil. |
| `GET` | `/api/v1/network/peers/` | JWT requis | Lister les appareils actifs, sans exposer leurs clés publiques. |

### 2. Client Flet

Dans un second terminal :

```bash
cd frontend

python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate

pip install flet httpx zeroconf aiortc
python main.py
```

### Moteur P2P par blocs

Le noyau réseau indépendant de Flet se trouve dans `core/p2p/`. Il calcule un
manifeste SHA-256, sert les blocs disponibles en TCP sur une adresse du LAN,
vérifie chaque bloc reçu et conserve les blocs validés dans un fichier `.part`
avec un journal atomique de reprise. Les fichiers finaux sont renommés après
validation complète. Le moteur n'est pas encore relié aux écrans Flet.

Exécuter les tests du moteur depuis la racine du dépôt :

```bash
python -m unittest discover -s tests -v
```

Le pair serveur doit être explicitement lié à son adresse LAN, par exemple
`192.168.1.25`; le client refuse les destinations IP publiques.

---

## Feuille de route

Durée prévue : **1,5 semaine**.

- [x] **Jours 1–2** — Architecture des dossiers, schéma de base Django, maquette Flet
- [x] **Jours 3–4** — Registre des nœuds et scanner UDP Zeroconf
- [ ] **Jours 5–7** — Transfert P2P par blocs (sockets TCP et cache anti-coupure)
- [ ] **Jours 8–9** — Signalisation WebSocket et appels WebRTC (Local Meet)
- [ ] **Jour 10** — Tests de charge en amphi, recette et livraison du binaire

---

## Licence et crédits

Projet développé par **Alexandre Dumas** et l'équipe Ingénierie Logicielle, **Groupe 9**.

Distribué sous licence MIT. Libre d'utilisation pour les établissements d'enseignement supérieur.
