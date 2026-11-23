# Mohamed Amine – « Jamais de blanc »

## État de la branche

Le chantier voix se trouve sur `mohamed-amine/voice-latency`. `TEAM_FILLERS=1` active les changements pour les essais. La prochaine étape est la comparaison au micro sur le pack du Fournil. [Fiche de tâches](../tasks/mohamed-amine.md) · [Décisions et résultats](../../../DECISIONS.md)

| Étape | Travail sur la branche | Validation restante |
|---|---|---|
| T0 · Référence | Protocole ci-dessous. Le kit local tourne avec les données et les fournisseurs de démonstration. | Relever S01 et S06 au micro sur le poste de l'équipe. |
| T1 · Phrases prêtes | À l'ouverture de la connexion, deux phrases sont synthétisées en arrière-plan avec la voix configurée et mises en mémoire. Le premier tour peut démarrer pendant la préparation. Une synthèse vide peut être retentée à la réouverture. Le test de la banque est actif. | Écouter la voix de l'équipe au premier appel. |
| T2 · Moment de parler | Une demande explicite de stock, de prix ou de commande peut déclencher une phrase déjà prête. Les ajouts en cours d'appel et les demandes comme « je veux 10 kg de farine » sont aussi reconnus. Une recherche ERP effective peut déclencher la phrase si la formulation a échappé à la détection. Les remerciements et salutations simples restent silencieux jusqu'à la réponse. | Valider la répartition avec Youssef. Mesurer le départ en moins de 300 ms et le premier son perçu en moins de 1 s sur S01/S05. |
| T3 · Clavier | Une recherche longue peut jouer quelques rafales de clavier espacées et une reprise unique de la quantité et du produit si la demande est claire. La réponse de l'agent ou une interruption annule les sons qui restent à jouer. Le test S10 interrompt une recherche en cours. Le segment se ferme aussi si le tour échoue. | Vérifier le niveau et l'arrêt à l'oreille pendant S10. |
| T4 · Doublons | Le lecteur écarte les annonces répétées en tête de réponse, y compris « Un instant, je vérifie », lorsqu'une annonce a déjà joué. | Avec Daycem, valider le ton et la consigne proposée ci-dessous. |
| T5 · Première phrase utile | La préparation utilise la connexion HTTP partagée du fournisseur. Une première proposition assez longue peut partir à la virgule. La mesure du premier octet de la synthèse reste distincte du premier son du tour. | Vérifier la prosodie et viser `ttsFirstByteMs < 300` dès le premier tour. |
| T6 · Transcription | Le jargon et les prénoms ERP ont priorité dans le vocabulaire transmis à la reconnaissance vocale. Le jargon de base reste disponible si l'ERP ne répond pas. | Dicter « dix de tradi », « tourage », « gruau », « T55 » et un prénom du pack à Soniox. |
| T7 · Fin de parole automatique (facultatif) | Décision de conserver Espace pour la démo. | Réexaminer la détection automatique après les essais au micro. |

## Décisions à partager

- **Youssef.** Tant que le routage commun reste à définir, la voix laisse l'orchestrateur prendre la parole dès que `TEAM_ORCHESTRATOR=1`. Une frappe reste possible sur une recherche effective avant toute parole du modèle. [Contrat entre les chantiers](../interfaces.md)
- **Daycem.** Proposition pour les règles vocales lorsque `TEAM_FILLERS=1` et que la couche voix gère l'attente : « Donne directement le résultat de ta vérification. Le lecteur vocal se charge de faire patienter le client. »

## Essai au micro

1. Charger le pack du Fournil en local et ouvrir la page Voix avec les fournisseurs de l'équipe. Avec les interrupteurs éteints, jouer S01 et S06. Relever par tour `sttMs`, `llmFirstTokenMs`, `ttsFirstByteMs`, `totalMs` et `perceivedMs`. Noter les fournisseurs et distinguer le premier tour des suivants.
2. Activer `TEAM_FILLERS=1`, redémarrer le service IA et rejouer S01, S05 et S06 dans les mêmes conditions. Relever quel son arrive en premier et à quel moment commence la réponse utile. Reporter médiane et pire cas dans [DECISIONS.md](../../../DECISIONS.md).
3. Sur S10, reprendre Espace **pendant** le premier son. Vérifier que l'ancien tour se coupe et que la nouvelle demande est transcrite. Sur S11, dire « C'est tout, merci. Au revoir. » et écouter la réponse directe. Le script rejoue les tours l'un après l'autre. Le test d'intégration exerce l'interruption et la fermeture du segment pendant un tour actif. [S10](../../../scenarios/S10.json) · [S11](../../../scenarios/S11.json) · [Tests voix](../../../apps/ai/tests/test_voice_fillers.py)


## Variante avec modèle rapide

Avec `TEAM_FILLERS=2`, « Je vais voir » ouvre l'attente. Le modèle rapide sélectionne un court passage de la transcription en parallèle avec l'agent ERP. La reprise utilise les mots du client. Une demande courte et ambiguë est reprise en entier pour garder les options et les négations. Une demande longue dont on risquerait de changer le sens reçoit « Un instant, je vérifie ». Seule la réponse finale de l'agent ERP est lue sur ces tours. La reprise en préparation est annulée si la réponse arrive ou si le client reprend la parole.

Pour comparer, garder les mêmes fournisseurs et `TEAM_ORCHESTRATOR=0`. Relancer l'IA entre `TEAM_FILLERS=1` et `TEAM_FILLERS=2`. Tester « Dix kilos de farine ou deux sacs ? » pendant une vérification assez longue, puis « Merci » pour vérifier la réponse directe. Le mode 2 utilise le modèle `TEAM_FAST_MODEL` du même fournisseur que l'agent principal, sans appel ERP supplémentaire.
