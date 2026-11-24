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
- En cours : T4 (deux cerveaux + Jev).
- Pour Daycem : S05·2 attend `get_price` mais `quote_line` (Amine K.) répond juste → ajouter `quote_line` à `tools_any` ;
  S05·1 « 82 » est dit en lettres (« quatre-vingt-deux ») → ajouter cette forme à `says_any`.
- Changement de contrat : `caller` accepte `resume` ; `caller_ready` renvoie `resume`. `TEAM_PRELOAD` ne sert plus
  qu'à l'identification automatique dans la conversation (sans formulaire).
- J'ai besoin de : **tout le monde → testez la page Voix en passant par « Qui appelle ? »** (obligatoire avant de parler).
- Interrupteur(s) : TEAM_PRELOAD = on · TEAM_PRODUCT_INSIGHT = on (après `make restart`) · TEAM_ORCHESTRATOR = off
- ⚠️ Pour tester S40 / la démo : `--reset` efface la promo de démo → relancer `scripts/setup_demo_data.py` après.
