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

## Structure du d?p?t

Le backend Django fournit l'indexation, l'authentification, le registre r?seau et la signalisation. Le client Flet, les services et les moteurs P2P/d?couverte sont ? la racine du d?p?t (l'arborescence `frontend/` d?crite historiquement n'est pas celle de l'impl?mentation actuelle).

```text
campus-share/
??? backend/                     # Django + DRF + Channels (API, registre, chat, signalisation)
?   ??? manage.py
?   ??? config/                  # settings, urls, asgi/wsgi, routing WebSocket
?   ??? apps/
?   ?   ??? authentication/      # Comptes, r?les, JWT, auth WebSocket
?   ?   ??? repository/          # Catalogue, manifestes SHA-256, seeders
?   ?   ??? network_registry/    # N?uds LAN, heartbeat, pr?sence
?   ?   ??? chat/                # Messages par UE (REST + WebSocket)
?   ?   ??? signaling/           # Signalisation salles/appels (REST + WebSocket)
?   ??? requirements.txt
??? core/
?   ??? p2p/                     # Manifeste, stockage reprenable, protocole TCP, scheduler
?   ??? discovery/               # D?couverte UDP des pairs (beacons LAN)
??? services/                    # Client backend, t?l?chargement, partage, ?tat local
??? views/                       # Vues Flet (cours, chat, appels/signalisation, param?tres)
??? components/                  # Composants UI Flet
??? tests/                       # Tests moteur/services/UI c?t? racine
??? main.py                      # Point d'entr?e client Flet
??? README.md
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

### REST (impl?ment? / principaux endpoints)

| M?thode | Endpoint | Description |
| --- | --- | --- |
| `POST` | `/api/v1/auth/register/`, `/login/`, `/refresh/`, `GET /me/` | Authentification JWT |
| `GET/POST` | `/api/v1/repository/resources/` et routes associ?es | Catalogue, manifestes, seeders, annonce de blocs |
| `GET/POST` | `/api/v1/network/nodes/`, `/peers/`, heartbeat/delete | Registre des n?uds LAN |
| `GET/POST` | `/api/v1/chat/<ue_code>/messages/` | Historique et envoi des messages de discussion par UE |
| `GET/POST` | `/api/v1/signaling/<room_id>/messages/` | Messages de signalisation par salle (polling/REST) |

### WebSockets (Channels)

| Route | Description |
| --- | --- |
| `ws://<server_ip>:8000/ws/chat/<ue_code>/` | Discussion temps r?el par UE (auth JWT via `?token=`) |
| `ws://<server_ip>:8000/ws/signaling/<room_id>/` | Relais/persistance des messages de signalisation (SDP/ICE, auth JWT via `?token=`) |

> Le client Flet actuel int?gre le chat et la signalisation principalement via REST/polling; le transport m?dia WebRTC (audio/vid?o/partage d'?cran) n'est pas finalis? c?t? client desktop.

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
| `GET` | `/api/v1/repository/resources/{id}/seeders/` | Pairs actifs qui annoncent des blocs de cette ressource. |
| `POST` | `/api/v1/repository/seeders/announce/` | Annoncer ou mettre à jour le bitfield d'un nœud possédé. |

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

L'interface Flet se lance depuis la racine du dépôt :

```bash
python -m pip install -r requirements.txt
python main.py
```

Dans **Paramètres**, saisir l'adresse LAN du backend, puis se connecter avec
son compte. Le catalogue réel se charge depuis l'écran **Cours & TP**. Le
bouton de téléchargement demande les seeders au backend puis transfère les
blocs directement en TCP; les fichiers sont enregistrés dans
`~/CampusShare/downloads` et le cache reprenable dans `~/CampusShare/cache`.
Pour qu'une ressource soit téléchargeable, au moins un appareil doit être
enregistré et annoncer ses blocs via l'API du registre et l'endpoint
`/api/v1/repository/seeders/announce/`.

Après un téléchargement terminé, CampusShare demande si tu veux partager cette
ressource. Le partage n'est activé qu'après confirmation; le consentement est
mémorisé localement dans `~/CampusShare/state.json` pour permettre de
ré-annoncer automatiquement les fichiers complets déjà présents dans le cache
lors des connexions suivantes. Le serveur TCP local et les annonces/heartbeats
s'arrêtent à la fermeture de l'application et le nœud local est désenregistré.

L'adresse IPv4 privée et l'identité du nœud sont gérées automatiquement. Si la
détection choisit la mauvaise interface ou échoue, définis `CAMPUSSHARE_NODE_IP`
avec l'adresse LAN de cet ordinateur avant de lancer `main.py`.

### Moteur P2P par blocs

Le noyau réseau indépendant de Flet se trouve dans `core/p2p/`. Il calcule un
manifeste SHA-256, sert les blocs disponibles en TCP sur une adresse du LAN,
vérifie chaque bloc reçu et conserve les blocs validés dans un fichier `.part`
avec un journal atomique de reprise. Les fichiers finaux sont renommés après
validation complète. L'ordonnanceur interroge le bitfield de chaque pair,
priorise les blocs rares, répartit les requêtes avec une limite par pair et
réessaie un bloc auprès d'un autre seeder après un échec. Le serveur TCP local
peut distribuer plusieurs ressources sur le même port; seuls les fichiers
téléchargés et explicitement acceptés sont annoncés aux autres appareils.

Exécuter les tests du moteur depuis la racine du dépôt :

```bash
python -m unittest discover -s tests -v
```

Le pair serveur doit être explicitement lié à son adresse LAN, par exemple
`192.168.1.25`; le client refuse les destinations IP publiques.

---

## Feuille de route (?tat)

- [x] Architecture, base Django/Flet, auth JWT, catalogue et registre r?seau
- [x] Moteur P2P TCP par blocs, manifeste SHA-256, cache/reprise, scheduler multi-pairs
- [x] Int?gration client (catalogue/t?l?chargement/partage opt-in), persistance consentement, auto-reshare
- [x] D?couverte UDP (module + int?gration de base dans le service de partage/UI param?tres)
- [x] Scaffolding chat et signalisation (REST + WebSocket backend, vues Flet bas?es sur API/polling, publication catalogue)
- [ ] Client m?dia WebRTC complet (audio/vid?o/partage d'?cran) et UX appels de bout en bout
- [ ] Validation finale multi-appareils sur LAN r?el, tests de charge en amphi, packaging/livraison binaire

> Remarque : les ?l?ments non coch?s n?cessitent des tests manuels sur mat?riel/r?seau r?el et/ou des composants m?dia suppl?mentaires.

---

## Licence et crédits

Projet développé par **Alexandre Dumas** et l'équipe Ingénierie Logicielle, **Groupe 9**.

Distribué sous licence MIT. Libre d'utilisation pour les établissements d'enseignement supérieur.
