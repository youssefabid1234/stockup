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
- En cours : T1 (super-outil produit) puis T4 (deux cerveaux + Jev).
- Changement de contrat : `caller` accepte `resume` ; `caller_ready` renvoie `resume`. `TEAM_PRELOAD` ne sert plus
  qu'à l'identification automatique dans la conversation (sans formulaire).
- J'ai besoin de : **tout le monde → testez la page Voix en passant par « Qui appelle ? »** (obligatoire avant de parler).
- Interrupteur(s) : TEAM_PRELOAD = on · TEAM_PRODUCT_INSIGHT / TEAM_ORCHESTRATOR = off
