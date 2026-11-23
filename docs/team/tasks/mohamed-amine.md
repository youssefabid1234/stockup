# Mohamed Amine – ⚡ « Jamais de blanc » (vitesse + voix)

**Critères du jury** : Rapide (fin de parole → premier son < 1,5 s) et Naturel.
**Interrupteur** : `TEAM_FILLERS`. **Branche** : `mohamed-amine/<sujet>` (ex. `mohamed-amine/fillers`).

## La vraie vie
Nadine demande « vous avez encore du tourage AOP ? ». Lucie répond **tout de suite** « Je regarde ça… », on entend son
clavier, puis elle donne la réponse. Jamais trois secondes de silence au téléphone.
Aujourd'hui l'agent met **≈ 4 s avant son premier mot** (mesuré sur S03 : 4,1 s) et **≈ 9 s** au total en vocal.

## Tes fichiers
| Fichier | Rôle |
|---|---|
| `apps/ai/app/services/fillers.py` | **à toi** : banque de phrases d'attente, bruit de clavier, décisions |
| `apps/ai/app/services/voice_session.py` | **à toi** (fichier du kit) : `Speaker.play_audio`, connexion TTS chaude ; les points d'appel `fillers.on_turn_start` / `on_tool_call` sont déjà branchés |
| `apps/ai/app/services/vocabulary.py` | **à toi** (fichier du kit) : vocabulaire envoyé à la transcription |
| `apps/ai/app/assets/` | **à toi** : son de clavier (mp3 court, libre de droits ou généré) |
| `apps/ai/app/clients/elevenlabs.py`, `soniox.py` | lecture seulement, sauf raison précise (FAQ : « déjà réglés ») |

Lis d'abord : `GUIDE-VOIX.md` §1 (anatomie d'un tour), §3 (mesures du kit), §4.7 (fillers), §4.8-4.9 (TTS), §5
(naturel), §8 (plan 24 h) ; [interfaces.md](../interfaces.md) §1.

## Tes tâches, dans l'ordre
| # | Tâche | Fini quand |
|---|---|---|
| T0 | Kit lancé sur ton PC ; page Voix : jouer S01 et S06 à voix haute ; noter `sttMs`, `llmFirstTokenMs`, `ttsFirstByteMs`, `totalMs`, `perceivedMs` (ligne « kit d'origine » de DECISIONS.md) | la ligne est remplie |
| T1 | `Speaker.play_audio(mime, data)` dans voice_session.py + `FillerBank.warm_up(tts)` (synthétiser chaque phrase **une fois** à l'ouverture de session, avec la voix de l'équipe) | `test_filler_bank_warms_up_every_phrase` (enlever le skip) passe |
| T2 | `on_turn_start` : jouer une phrase d'attente **< 300 ms** après le relâchement, **seulement** si le tour va appeler des outils (règle anti-chevauchement, interfaces §1, à décider avec Youssef) | perçu < 1 s sur S01/S05, aucune phrase d'attente sur « merci » |
| T3 | `on_tool_call` : bruit de clavier pendant les recherches ERP, coupé dès que la vraie réponse commence | à l'écoute : naturel, pas de son par-dessus la voix |
| T4 | Éviter les doublons : quand `TEAM_FILLERS=1`, l'agent ne doit plus dire lui-même « Je regarde. » (VOICE_RULES l'y autorise) → proposer à Daycem la phrase à ajouter dans ses règles | plus de double « je regarde » |
| T5 | TTS : connexion gardée chaude (GUIDE-VOIX §4.9), première phrase coupée plus tôt (§4.8) | `ttsFirstByteMs` < 300 ms dès le 1er tour |
| T6 | Vocabulaire STT : ajouter le jargon (« tradi », « tourage », « chocolatine », « gruau », « T55 »…) et les prénoms des contacts dans `vocabulary.py` | dicté à voix haute, « dix de tradi » est bien transcrit |
| T7 | (si le temps) VAD / fin de parole automatique (§4.2), en gardant Espace pour la démo | décision notée dans DECISIONS.md |

**Tes scénarios** (S10–S19, au moins 2) : par exemple un client qui coupe la parole à l'agent (barge-in), et une
question très courte (« c'est tout, merci ») qui ne doit déclencher aucune phrase d'attente.

## Avec qui te coordonner
- **Youssef** : qui parle en premier (phrase d'attente ou agent rapide) → interfaces §1, à H+2.
- **Daycem** : le ton des phrases d'attente et la consigne qui empêche l'agent de dire « je regarde » lui-même.

## Pièges
- Une phrase d'attente sur un tour qui aurait répondu en 600 ms **ralentit** l'agent : mesure avant/après.
- Les phrases d'attente ne contiennent **jamais** de chiffre ni de promesse.
- Après chaque changement : rejouer S01, S05, S06 (`--voice` pour les vrais temps) et noter les chiffres.

## Le premier message à donner à ton IA de code
> Lis AGENTS.md, docs/team/README.md, docs/team/interfaces.md et docs/team/tasks/mohamed-amine.md. Je suis Mohamed
> Amine. Explique-moi T0 et T1 en mots simples, propose un plan, et attends mon accord avant de coder. Ne touche qu'à
> mes fichiers.
