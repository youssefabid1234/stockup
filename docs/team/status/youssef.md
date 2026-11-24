# Youssef – ⚡ Plusieurs cerveaux (orchestrateur, fiche préchargée, super-outil)  ·  mis à jour mar. 24/11

- Fait depuis la dernière sync :
  - **« Qui appelle ? » avant l'appel** (PR #9) : 1re réplique S01 7,7 s → 3,5 s (/chat), 6,9 s → 3,9 s en voix.
  - **Corrigé : « l'agent oublie qui appelle pendant l'appel »** (vu en test d'équipe). Deux causes :
    1. chez qui n'avait pas `TEAM_PRELOAD=1` dans son `.env`, le nom s'affichait en haut mais la fiche n'était pas
       donnée à l'agent → **l'appelant choisi dans le formulaire est maintenant toujours transmis** (sans interrupteur) ;
    2. si le service IA redémarre en plein appel (git pull, fichier enregistré : uvicorn --reload), il perdait
       l'appelant → **la page renvoie l'appelant à chaque reconnexion** (`resume`, la conversation à l'écran est gardée).
    Vérifié en vrai : interrupteur éteint + redémarrage en plein appel → l'agent sait toujours « Nadine Sarrailh ».
  - Fiche en cache copiée par appel (Guy puis Nadine pour la même boulangerie ne se mélangent plus).
  - **T1 super-outil produit (`product_insight`)** : stock + arrivages + prix du client + remplaçants classés (règles de
    Daycem) avec leur prix et leur promo, en un appel. 1re réplique : S05 6,2 → 3,9 s, S40 4,3 → 3,4 s, S04 4,1 → 3,5 s
    (médianes) ; l'agent cite la promo exacte. Allumé par défaut dans `.env.example`.
  - **Mains libres (page Voix, idée 1 + 2)** : plus besoin de maintenir Espace : le micro reste ouvert, début et fin de parole détectés (pause ≈ 0,65 s), et parler pendant que l'agent parle le coupe. Bouton « Mains libres » (allumé par défaut), Espace marche toujours. ⚠️ Mohamed Amine : ça touche ta page Voix (useVoiceSession : readRms, stopTalking({quiet})), relis stp.
  - **Écoute robuste (mains libres)** : plus aucun morceau perdu (les phrases dites avant la réponse sont réunies en un
    seul message, même coupées en pleine transcription), voix multiples séparées par Soniox ([appelant] / [autre voix])
    et mots douteux marqués « mot(?) » → l'agent ignore les autres voix, garde la dernière correction, redemande un mot
    douteux. Vérifié en vrai (2 voix ElevenLabs → Soniox ; 3 réponses de l'agent). ⚠️ Mohamed Amine : touche
    voice_session (Conversation.pending), utterance.py, soniox.py (enable_speaker_diarization) : relis stp.
  - **ERP en anglais** : `data/seed_en/` dans git (toutes les données traduites, ID intacts) ; s'active avec
    `SEED_DIR_NAME=seed_en` dans `.env`. ⚠️ Pour l'agent/branche anglaise : le code qui lit du FRANÇAIS dans les données
    doit suivre : `rules_sales.substitution_policy` (« refuse/accepte les substitutions » → « never any substitution »,
    « accepts … substitutions »), `call_context` (« Fermé le <jour> » → « Closed on <day>s »), `rules_order` (alias et
    mots d'emballage « sac/carton/plaque » → « bag/carton/sheet »), et les phrases générées par l'ERP lui-même
    (`apps/backend`, ex. « Règle « … » : -8 % sur prix catalogue »). Noms des produits : `data/seed_en/GLOSSARY.md`.
- En cours : T4 (deux cerveaux + Jev).
- Pour Daycem : S05·2 attend `get_price` mais `quote_line` (Amine K.) répond juste → ajouter `quote_line` à `tools_any` ;
  S05·1 « 82 » est dit en lettres (« quatre-vingt-deux ») → ajouter cette forme à `says_any`.
- Changement de contrat : `caller` accepte `resume` ; `caller_ready` renvoie `resume`. `TEAM_PRELOAD` ne sert plus
  qu'à l'identification automatique dans la conversation (sans formulaire).
- J'ai besoin de : **tout le monde → testez la page Voix en passant par « Qui appelle ? »** (obligatoire avant de parler).
- Interrupteur(s) : TEAM_PRELOAD = on · TEAM_PRODUCT_INSIGHT = on (après `make restart`) · TEAM_ORCHESTRATOR = off
- ⚠️ Pour tester S40 / la démo : `--reset` efface la promo de démo → relancer `scripts/setup_demo_data.py` après.
