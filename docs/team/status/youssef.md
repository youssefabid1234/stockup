# Youssef – ⚡ Plusieurs cerveaux (orchestrateur, fiche préchargée, super-outil)  ·  mis à jour mar. 24/11 0h00

- Fait depuis la dernière sync :
  - **T2 fiche client préchargée** (`TEAM_PRELOAD`, **éteint par défaut**) : identification du client dans la conversation,
    chargement en arrière-plan + cache 5 min, stock du panier habituel, notes « Fermé le <jour> » retirées quand l'ERP
    livre ce jour, fiche ajoutée à la fin du prompt. Branchée dans `loop.py` (marche en voix, chat et rejeu). 6 tests.
  - Mesures (DECISIONS.md §4) : 9/9 réussies dans les deux cas ; **pas de gain de vitesse mesurable** aux tours 2+
    (l'agent ne recherchait déjà plus le client) ; S02 meilleur (modifie la ligne au lieu de tout relire).
  - `docs/team/ideas.md` : file d'idées par priorité (voix française, Jev, données, appels sortants…).
- En cours : proposer la suite à l'équipe : identifier le client dès le 1er tour (le vrai temps perdu) puis T1.
- Bloqué / j'attends : rien.
- J'ai besoin de :
  - **Amine K.** : toujours la règle explicite « jours ERP font foi » dans `ORDER_RULES` : en S05 l'agent lit la note
    « Fermé le mercredi » via `get_context` au 1er tour (avant que la fiche existe) et demande « vous êtes bien ouvert ? ».
  - **Mohamed Amine** : la voix française jugée peu naturelle → idée n°1 de `docs/team/ideas.md`.
- Interrupteur(s) : TEAM_PRELOAD prêt mais **à ne pas allumer sur main** pour l'instant (aucun gain mesuré) ;
  TEAM_PRODUCT_INSIGHT / TEAM_ORCHESTRATOR = off.
- Mesure : 1er tour S01 ≈ 7 s (inchangé) · tours suivants ≈ 2-5 s
- Changement de contrat demandé : aucun (`load_call_context` / `render_for_prompt` inchangés ; ajout de
  `context_for`, `prefetch`, `identify_client`)
