# Équipe 12 – Le Fournil Occitan : le plan

> Point d'entrée de l'équipe. Humains et IA de code le lisent **avant** de toucher au code, avec
> [AGENTS.md](../../AGENTS.md) (règles), [interfaces.md](interfaces.md) (les contrats entre nous) et **sa fiche**
> dans [tasks/](tasks/).
> Rendu : **mardi 24/11 17h30, sans exception** (repo + vidéo). Démo devant le jury à 18h.

---

## 1. Ce qu'on construit

**Le standard téléphonique du Fournil Occitan.** Un client (boulangerie, pâtisserie, restaurant…) appelle ; l'agent
vocal prend sa commande comme le ferait la meilleure standardiste : il le reconnaît, sait ce qu'il commande d'habitude,
comprend le jargon (« 10 de tradi » = 10 sacs de 25 kg), vérifie le stock et le compte, gère une rupture en proposant
**et en argumentant** un remplaçant **seulement si le client les accepte**, relit la commande, puis la saisit dans l'ERP.
Ensuite (si le temps le permet) : réclamations et questions dans le même appel.

**Pourquoi (dans les données)** : 45 % des commandes arrivent par téléphone (11 231 / 24 769), surtout entre 12h et 15h,
toutes retapées à la main par les commerciaux et le standard. Un boulanger a les mains dans la farine : il appelle.

**Ce qu'on vise** (critères du jury) : **intelligent** (jamais faux, jamais inventé), **rapide** (moins de 1,5 s entre la
fin de la phrase du client et le premier son), **naturel** (on oublie que c'est une machine). La démo vient **après** le
produit.

## 2. Le parcours d'un appel et qui possède quoi

```
Client parle (page Voix, Espace)
  │
  ├─ STT Soniox (texte en direct) ················ Mohamed Amine : vocabulaire métier (vocabulary.py)
  │
  ▼  fin de phrase (t0)
  ├─ ⚡ 0-300 ms : phrase d'attente / bruit de clavier ··· Mohamed Amine (services/fillers.py)
  │
  ├─ 🧠 Agents en parallèle ························ Youssef (agent/orchestrator.py)
  │     ├─ agent « parole » rapide (Haiku) : répond vite aux tours simples
  │     └─ agent « cerveau » (Sonnet) : outils + décisions
  │
  ├─ Fiche client chargée une seule fois, en parallèle ··· Youssef (agent/call_context.py)
  ├─ Super-outil produit (stock + prix + remplaçants + promos) ··· Youssef (tools/product_insight.py)
  │
  ├─ Règles « commande juste » (jargon, comme d'hab, relecture, blocage, jours) ··· Amine Khalil (agent/rules_order.py)
  ├─ Règles « bon vendeur » (préférences, remplacement avec accord, argumenter, ton) ··· Daycem (agent/rules_sales.py)
  │
  ▼
  ├─ ERP : brouillon → relecture → confirmation (outils du kit) · rien à coder
  └─ TTS ElevenLabs phrase par phrase, connexion chaude ··· Mohamed Amine (voice_session.py / clients TTS)
```

Tout est **désactivé par défaut** (interrupteurs `TEAM_*` dans `.env`, voir [interfaces.md](interfaces.md)) : le kit
d'origine tourne tant qu'une brique n'est pas prête. Chacun active la sienne quand elle marche.

## 3. Les 4 chantiers

| Qui | Chantier | Critère | Fiche |
|---|---|---|---|
| **Mohamed Amine** | ⚡ « Jamais de blanc » : phrases d'attente, bruit de clavier, TTS chaud, vocabulaire STT, mesures | Rapide + Naturel | [tasks/mohamed-amine.md](tasks/mohamed-amine.md) |
| **Youssef** | ⚡ « Plusieurs cerveaux » : orchestrateur rapide/cerveau, fiche client préchargée, super-outil, rejeu des scénarios | Rapide + Intelligent | [tasks/youssef.md](tasks/youssef.md) |
| **Amine Khalil** | 🧠 « La commande juste » : jargon et unités, comme d'hab, changements d'avis, relecture, blocage / jours / heure limite | Intelligent | [tasks/amine-khalil.md](tasks/amine-khalil.md) |
| **Daycem** | 🧠 « Le bon vendeur » : préférences, remplacement avec accord, argumenter une alternative, promo de démo, ton par client | Intelligent + Naturel | [tasks/daycem.md](tasks/daycem.md) |

**Pour tous** : écrire **2 scénarios** de son domaine dans [`scenarios/`](../../scenarios/) (les tests de toute la nuit),
jouer le client à voix haute pour tester les autres, noter ses mesures et ses choix dans `DECISIONS.md`.

## 4. Jalons

| Heure (mar. 24/11 = J) | Jalon | Vérifié par |
|---|---|---|
| H+1 | Chacun a lu sa fiche, kit lancé sur son PC, 2 scénarios écrits | `scripts/run_scenarios.py` les liste |
| H+4 | Chaque brique en v0 derrière son interrupteur, tests verts | `uv run --group dev pytest` |
| H+8 | Un appel complet (scénario S1) passe avec toutes les briques actives | rejeu des scénarios + page Voix |
| H+14 | Scénario « rupture + remplaçant argumenté » et « client bloqué » passent ; < 1,5 s perçu | mesures dans DECISIONS.md |
| J 13h | Extension réclamations si ok ; sinon polish | |
| **J 14h30** | **Gel du code** : uniquement des corrections | |
| J 14h30–17h | Démo : vidéo, slides, README, test `make setup` (Mac/Docker) | |
| **J 17h30** | **Rendu** | |

## 5. Rituel toutes les heures : « sync »

Toutes les heures pile (ou quand quelqu'un écrit « sync » dans le groupe), chacun :

1. **Fige** : son code tourne (le reste derrière son interrupteur), `uv run --group dev pytest -q` est vert.
2. **Statut** : met à jour `docs/team/status/<prénom>.md` (fait / en cours / bloqué / besoin des autres / mesure).
3. **Explique** : son IA lui résume ce qui a changé ; **il valide** (règle 0 d'AGENTS.md).
4. **Pousse** sa branche, ouvre / met à jour sa PR vers `main`.
5. **Fusionne** si ça tourne (un coéquipier jette un œil). `main` doit toujours marcher.
6. **Récupère** `main` dans sa branche et lit les statuts des autres.

Claude Code : `/sync`. Codex : « sync ». Détail dans [AGENTS.md](../../AGENTS.md#team-12--règles-déquipe).

## 6. Ce qu'on garde de notre premier travail (repo amine-ml/Stockline-Hackathon)

| Idée | Où elle sert ici |
|---|---|
| « Ne jamais inventer », « n'engager qu'avec un humain » | rules_order.py / rules_sales.py |
| « Comme d'hab », corrections dans le même message, unités et conversions (Amine K.) | rules_order.py |
| Devis → « oui » → confirmé | relecture orale avant `confirm_order` |
| Mémoire / historique client | call_context.py (fiche préchargée) |
| Tests de cas limites avec sorties commentées (`try_message.py`) | `scripts/run_scenarios.py` + `scenarios/` |
