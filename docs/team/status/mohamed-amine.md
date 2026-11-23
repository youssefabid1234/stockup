# Mohamed Amine – « Jamais de blanc »

## Statut

- Fait depuis la dernière sync — fiche de tâches, règles d'équipe et code vocal existant relus. Plan de reprise préparé sur `mohamed-amine/voice-latency`.
- Prochaine étape — T0, mesurer S01 et S06 sur la page Voix avec le kit d'origine.
- Dépendances — le pack et la configuration locale de l'équipe pour T0. Pour T2, se mettre d'accord avec Youssef sur qui parle en premier. Pour T4, convenir avec Daycem du ton et de la consigne contre les doublons.
- Interrupteur — `TEAM_FILLERS` démarre éteint. L'activer localement pour comparer les deux versions.
- Mesures — T0 à relever. Le chiffre déjà consigné sur S03 vient du chat et ne sert pas de référence vocale. [DECISIONS.md](../../../DECISIONS.md)

## Objectif

Sur le standard de **Le Fournil Occitan**, donner un premier son en **moins de 1,5 s** après le relâchement d'Espace. Si une vérification prend du temps, une courte phrase d'attente peut faire patienter le client. Un tour simple comme « merci » doit rester fluide. [Plan d'équipe](../README.md) · [Fiche de tâches](../tasks/mohamed-amine.md)

## Étapes dans l'ordre

- [ ] **T0 — Mesurer le kit.** Depuis le kit en local, avec `TEAM_FILLERS` éteint, jouer S01 et S06 au micro sur la page Voix. Relever `sttMs`, `llmFirstTokenMs`, `ttsFirstByteMs`, `totalMs` et `perceivedMs` par tour. Consigner la médiane et le pire cas dans la ligne « Kit d'origine » de [DECISIONS.md](../../../DECISIONS.md).
- [ ] **T1 — Préparer les phrases à l'ouverture de l'appel.** Compléter `FillerBank.warm_up(tts)` pour synthétiser chaque phrase une fois à l'ouverture avec la voix de l'équipe, puis la garder en mémoire. Ajouter `Speaker.play_audio(mime, data)` pour réutiliser le segment audio du tour sur la page Voix. Enlever le marqueur d'ignorance du test `test_filler_bank_warms_up_every_phrase` et vérifier qu'il passe. [fillers.py](../../../apps/ai/app/services/fillers.py) · [voice_session.py](../../../apps/ai/app/services/voice_session.py)
- [ ] **T2 — Choisir quand faire patienter.** Avec Youssef, convenir d'une règle avant de compléter `on_turn_start`. Émettre une phrase seulement si le tour devrait appeler des outils et laisser la priorité à l'agent rapide s'il répond en moins de 700 ms. Viser le début de la phrase à moins de 300 ms du relâchement et un premier son perçu en moins d'une seconde sur S01/S05. Vérifier à l'oreille qu'un « merci » ne déclenche rien. [Contrat voix et tour de parole](../interfaces.md#1-voix--tour-de-parole-mohamed-amine--youssef)
- [ ] **T3 — Jouer le clavier pendant les recherches.** Compléter `on_tool_call` en réutilisant le point d'appel existant. Générer un son court ou le charger localement. Vérifier qu'il s'arrête dès que la réponse démarre ou que le client reprend la parole. [Règles de dépôt](../../../AGENTS.md)
- [ ] **T4 — Éviter les phrases en double.** Proposer à Daycem une consigne pour que le modèle laisse au lecteur audio le soin de dire « Je regarde » lorsque `TEAM_FILLERS` est actif. Écouter le résultat sur un tour avec recherche.
- [ ] **T5 — Accélérer la première phrase utile.** Réutiliser la connexion HTTP partagée d'ElevenLabs et vérifier que la préparation de T1 la rend disponible dès le premier tour. Essayer une coupure plus tôt sur la première phrase si la voix reste naturelle. Mesurer `ttsFirstByteMs` sur la première synthèse de la réponse, avec une cible de 300 ms. [Guide voix](../../../GUIDE-VOIX.md)
- [ ] **T6 — Améliorer la transcription.** Enrichir `vocabulary.py` avec « tradi », « tourage », « chocolatine », « gruau », « T55 » et les prénoms disponibles côté ERP. Vérifier au micro « dix de tradi » et quelques termes du Fournil, en tenant compte de la limite de vocabulaire de Soniox. [vocabulary.py](../../../apps/ai/app/services/vocabulary.py)
- [ ] **T7 — Détecter la fin de parole si le temps le permet.** Tester la détection automatique après les mesures et les scénarios prioritaires. Garder Espace disponible pour la démo et consigner la décision dans [DECISIONS.md](../../../DECISIONS.md).

## Vérifications à chaque changement

- Rejouer S01, S05 et S06 sur les données locales. Comparer avec et sans `TEAM_FILLERS` dans les mêmes conditions. Noter si le premier son est une phrase d'attente, le clavier ou le début de la réponse utile.
- Écrire S10 (le client coupe l'agent pendant qu'il parle) et S11 (le client dit « c'est tout, merci »). Vérifier que le son s'arrête aussitôt sur S10 et qu'aucune phrase d'attente ni bruit de clavier ne joue sur S11.
- Utiliser le script `--voice` pour les temps côté serveur et les appels aux outils. Il envoie des répliques sous forme de texte et ignore les octets audio. Utiliser le micro et la page Voix pour mesurer `sttMs` et `perceivedMs`, écouter les chevauchements et tester l'interruption en direct. [Format des scénarios](../../../scenarios/README.md) · [Script de rejeu](../../../scripts/run_scenarios.py)
- Lancer les tests IA (`make test`), tenir ce statut à jour et ajouter les mesures et les choix dans la section « Vitesse et voix » de [DECISIONS.md](../../../DECISIONS.md).
