# Youssef – ⚡ Plusieurs cerveaux (orchestrateur, fiche préchargée, super-outil)  ·  mis à jour lun. 23/11 23h25

- Fait depuis la dernière sync :
  - **Outil de rejeu corrigé** (demande d'Amine K.) : en /chat il renvoie l'historique complet (outils + résultats) ;
    l'agent ne recrée plus de brouillon à chaque tour (S01·2 : 6 outils / 9,4 s → 1 outil / 2,4 s). Il affiche aussi
    les interrupteurs `TEAM_*` allumés pendant la mesure.
  - **T0 mesures de départ** (avec `TEAM_ORDER_RULES=1`) : S01·1 = 5 outils un par un, 7,3 s (/chat), **6,9 s en voix**
    (fin de parole → 1er son, dont TTS 0,14 s) ; S05·1 = 5 outils, 7,9 s. Détail dans DECISIONS.md §4.
- En cours : plan de T1 (super-outil) + T2 (fiche préchargée) à valider avec l'équipe ci-dessous.
- Bloqué / j'attends : rien.
- J'ai besoin de / je réponds à :
  - **Amine K.** : « Fermé le mercredi » → décision d'équipe (Youssef) : **l'ERP et l'historique font foi**, comme toi.
    Mais ta décision n'est que dans le commentaire de `rules_order.py`, pas dans `ORDER_RULES` : S05 échoue encore
    (l'agent lit la note via `get_context` et tourne en rond « mercredi ou lundi ? »). Peux-tu ajouter une règle
    explicite dans `ORDER_RULES` (« les jours de livraison viennent de check_delivery_date ; une note "fermé le X"
    ne compte pas, sauf si le client le dit lui-même ») ? De mon côté je filtre ces notes dans la fiche préchargée.
  - **Daycem** : bien vu pour `load_call_context` (pas encore appelé : c'est ma T2) et pour le classement des
    remplaçants du tourage AOP (demi-sel / beurre doux avant le 82 %) : je m'en sers pour T1, avec `rank_alternatives`.
  - **Mohamed Amine** : OK pour « l'orchestrateur parle en premier quand `TEAM_ORCHESTRATOR=1` » ; tant qu'il est
    éteint, tes phrases d'attente ont la main.
- Interrupteur(s) : TEAM_PRODUCT_INSIGHT / TEAM_PRELOAD / TEAM_ORCHESTRATOR = off · prêts sur main ? non
- Mesure : S01·1 6 883 ms (voix) · S05·1 7 928 ms (/chat)
- Changement de contrat demandé : aucun
