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

python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate

pip install -r requirements.txt

python manage.py migrate
python manage.py runserver 0.0.0.0:8000
```

Le serveur écoute sur toutes les interfaces du LAN, port **8000**.

### 2. Client Flet

Dans un second terminal :

```bash
cd frontend

python -m venv venv
source venv/bin/activate          # Windows : venv\Scripts\activate

pip install flet httpx zeroconf aiortc
python main.py
```

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
