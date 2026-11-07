# TTA
🎓 CampusBot — Description Technique
📄 Présentation du Projet
CampusBot est un assistant virtuel intelligent (FAQ universitaire) conçu pour automatiser les réponses aux questions fréquentes des étudiants (inscriptions, emplois du temps, frais d'scolarité, procédures administratives).

Le système s'appuie sur une approche RAG (Retrieval-Augmented Generation) hybride : il interroge d'abord une base de connaissances locale stockée sous forme d'empreintes vectorielles, puis utilise un Modèle de Langage (LLM) via API pour synthétiser et reformuler une réponse fluide et adaptée.

🏗️ Architecture Globale & Stack Technique
Le projet repose sur une architecture client-serveur découplée :
[ Application Mobile ] <---> [ API Rest Django ] <---> [ PostgreSQL + pgvector ]
  (React Native)              (RAG / LangChain)              (Embeddings FAQ)
                                     |
                                     v
                              [ API LLM Extérieure ]
                              (Gemini / OpenAI)
Stack Technique
Frontend : React Native (avec Expo ou CLI), TypeScript / JavaScript.

Backend : Python 3.10+, Django Framework & Django REST Framework (DRF).

Base de données : PostgreSQL avec extension pgvector (recherche par similarité cosinus).

IA & ORM Vectoriel : LangChain (ou LlamaIndex), OpenAI API / Google Gemini API, Sentence-Transformers.

Authentification & Quotas : Django Knox / JWT (JSON Web Tokens), django-ratelimit pour la gestion des quotas de requêtes.

🧪 Stratégie de Test & Livrables
Livrables :

Application Mobile : APK Android / Build iOS.

Base de Données : Script SQL de migration et jeu de données (FAQ fictive de 30 à 50 entrées au format .json).

Rapport de Tests : Tests d'intégration API REST, mesure du temps de réponse de la recherche vectorielle, validation de la gestion des erreurs et des quotas API.

