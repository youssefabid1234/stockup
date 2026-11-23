# Youssef – ⚡ Plusieurs cerveaux (orchestrateur, fiche préchargée, super-outil)  ·  mis à jour mar. 24/11 0h30

- Fait depuis la dernière sync :
  - **« Qui appelle ? » avant l'appel** (page Voix) : formulaire obligatoire (client de l'ERP par nom / ville / téléphone +
    contact au téléphone, ou « Nouveau client ») puis « Démarrer l'appel » → fiche chargée avant le 1er mot.
    **1re réplique S01 : 7,7 s → 3,5 s (/chat), 6,9 s → 3,9 s en voix.** Détail : DECISIONS.md §4.
  - `TEAM_PRELOAD=1` par défaut dans `.env.example` → **ajoutez `TEAM_PRELOAD=1` dans votre `.env`** puis `make restart`.
  - Outil de rejeu : le client du scénario (`"client"`) est annoncé avant l'appel (`--no-caller` pour l'ancien
    comportement).
- En cours : T1 (super-outil produit), puis T4 (deux cerveaux + Jev).
- **Changement de contrat (prévenez-moi si gênant)** :
  - WS `/voice` : nouveau message client → serveur `{"type":"caller", clientId?, contactName?, phone?, companyName?,
    isNew?}` et réponse `{"type":"caller_ready", …}` (`schemas/voice.py` + `packages/shared/src/ai.ts`).
  - `POST /chat` : champ optionnel `callerClientId`.
  - Sur la page Voix, on ne peut plus parler avant d'avoir identifié l'appelant (bouton « Démarrer l'appel »).
- J'ai besoin de / je préviens :
  - **Mohamed Amine** : j'ai ajouté dans `voice_session.py` le cas `CallerMessage` et une méthode `set_caller`
    (rien d'autre touché) ; ça ne change pas tes annonces.
  - **Amine K.** : avec l'appelant annoncé, ton S02 tour 1 « échoue » seulement parce qu'il attend `get_client` /
    `get_client_history` : l'agent n'a plus besoin de chercher le client. Tu peux ajouter `check_delivery_date` (ou
    `create_draft_order`) à `tools_any`. Et toujours la règle « jours ERP font foi » dans `ORDER_RULES` (sans fiche).
  - **Daycem** : la fiche donne maintenant les préférences et le stock du panier habituel dès la 1re réplique (S05 :
    la note « Fermé le mercredi » ne perturbe plus l'agent).
- Interrupteur(s) : TEAM_PRELOAD = **on** (prêt pour main) · TEAM_PRODUCT_INSIGHT / TEAM_ORCHESTRATOR = off
- Mesure : 1re réplique S01 3,5 s (/chat) · 3,9 s voix
