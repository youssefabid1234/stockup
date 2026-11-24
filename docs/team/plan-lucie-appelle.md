# Lucie appelle elle-même, et laisse un message si personne ne décroche

**Branche** `youssef/lucie-appelle` · **Porteur** Youssef · **Base** le travail de Mohamed Amine (#44, `TEAM_OUTBOUND_DEMO`)

## 0. Ce qui existe déjà (vérifié le 24/11 à 13 h, main `86c6e26`)

| Brique | Où | État |
|---|---|---|
| Choix de l'offre (promo sur un achat habituel, nouveauté…) | `backend/services/recommendations.py` (`select`, `fresh_offer`) | ✅ 9 tests ERP OK |
| Tentative d'appel : sonne → décroché / sans réponse → terminé | `backend/services/outbound_calls.py`, routes `/api/outbound-demo/*` | ✅ API active, 4 clients éligibles |
| Sonnerie dans la page, décrocher = session vocale avec l'offre | `web/pages/voice/outbound.tsx`, `ai/services/voice_offers.py` | ✅ |
| SMS si sans réponse | `_missed()` : **gabarit fixe, affiché dans la page (simulé)** | ⚠️ ni écrit « par Lucie », ni envoyé |

**Ce qui manque pour le « waouh »** : (1) c'est un humain qui clique « Lancer un appel », pas Lucie qui décide ; (2) le message est un gabarit froid ; (3) rien n'arrive sur un vrai téléphone.

## Fait (24/11 après-midi) : lots A et B, version « démo sur la plateforme »

- **Lucie planifie** (`backend/services/outbound_plan.py`, `GET /api/outbound-plan`) : pour chaque client joignable
  avec une offre vérifiée, *qui* (meilleure offre par client, 4 au plus), *pourquoi* (achats récents, dernier achat,
  promo et date de fin, interlocuteur) et *à quelle heure* (30 min avant son heure habituelle de commande, sinon
  prochain créneau libre, 5 min d'écart ; le 1er au plus tôt dans `TEAM_OUTBOUND_FIRST_CALL_MIN` minutes). Sans modèle.
- **Page Voix, colonne de droite « Appels planifiés par Lucie »** : à l'heure prévue, si la page est ouverte, l'appel
  sonne tout seul ; « Appeler maintenant » sur chaque ligne ; « Replanifier ». Décrocher → on joue le client, Lucie
  présente l'offre (parcours de Mohamed Amine, inchangé).
- **Sans réponse → message vocal de Lucie** (`ai/services/outbound_message.py`, `POST /outbound/voicemail/{id}`) :
  rédigé par le modèle rapide avec ses règles de parole, prix dit comme en appel, chaque nombre contrôlé en code (sinon
  phrase fixe), dit avec sa voix ; la conversation du client s'ouvre dans la page (bulle vocale + transcription + lien
  fiche client) et l'historique client garde le message. Mesuré : ~3,5 s, message de 16 s.
- Pas de C ni de D (décidé avec Youssef) : pas de vrai SMS ni de vrai appel téléphonique.

## 1. Ce que le jury verra (démo de 60 s)

1. Page Voix : bandeau **« Lucie appelle Au Fournil de Sandrine : elle prend ce beurre chaque semaine, il est en promo jusqu'au 30/11 »**. Personne n'a cliqué.
2. Le jury laisse sonner. **Son vrai téléphone vibre** : SMS (ou WhatsApp) écrit dans le style de Lucie :
   « Bonjour Sandrine, c'est Lucie du Fournil Occitan. Votre beurre de tourage 82 % est à 8,46 € le kilo jusqu'au 30/11. Je vous en mets de côté ? Rappelez-nous au 05 61 … ou répondez à ce message. »
3. Option : **le téléphone sonne vraiment** (appel Twilio, Lucie annonce l'offre), puis SMS si pas de réponse.

## 2. Lots (dans l'ordre, chacun livrable seul)

| Lot | Quoi | Fichiers (nouveaux surtout) | Fini quand | Temps |
|---|---|---|---|---|
| **A · Lucie décide** | `TEAM_OUTBOUND_AUTO=1` : la boucle `process_due` lance elle-même la meilleure tentative (premier candidat de `candidates()`), avec la raison en clair. Garde-fous : heures 8 h-18 h (horloge métier), un appel à la fois (déjà), une tentative par client et offre (déjà), au plus 3 par campagne, bouton Pause. | `backend/services/outbound_auto.py`, un appel dans `process_due`, bandeau dans `outbound.tsx` | Sans clic, la page sonne avec la raison affichée ; Pause l'arrête | 40 min |
| **B · Message écrit par Lucie** | Route IA `POST /outbound/message` : le modèle rapide (Haiku) rédige le SMS à partir de **champs vérifiés** (prénom du contact, produit, raison, prix, date de fin, entreprise, numéro de rappel). Règles reprises de `listening.STYLE_RULES`, version écrite : 2 phrases, vouvoiement, une seule demande d'action, rien d'inventé. **Contrôle en code** : chaque nombre ou date du texte doit venir des champs, sinon gabarit actuel. `_missed()` l'appelle (2 s maxi). | `ai/services/outbound_message.py`, `ai/api/outbound.py`, petit crochet dans `_missed()` | Message naturel et personnalisé ; un chiffre inventé → retombe sur le gabarit | 40 min |
| **C · Vrai message** | Adaptateur `messaging.py` : `dry_run` (par défaut, la boîte actuelle), `twilio_sms`, `twilio_whatsapp`. **Envoi seulement à `TEAM_OUTBOUND_TEST_PHONE`** (le téléphone de démo), jamais aux numéros fictifs du pack. On garde le statut (envoyé / échec + identifiant fournisseur) sur la tentative et dans l'historique client (CRM). | `backend/services/messaging.py`, `.env.example` (noms des variables seulement) | Laisser sonner → le vrai téléphone reçoit un seul SMS, même après rechargement | 40 min |
| **D · Option : le vrai téléphone sonne** | Appel Twilio vers le téléphone de démo, avec un texte TwiML `<Say language="fr-FR">` reprenant la phrase d'ouverture de Lucie. On interroge le statut de l'appel (pas d'URL publique nécessaire). `no-answer` ou `busy` → lot C. Un vrai dialogue au téléphone (audio dans les deux sens) est **hors délai** : c'est le lot E du plan de Mohamed Amine. | `backend/services/telephony.py` | Le téléphone sonne ; sans réponse → SMS | 45 min |

## 3. Choix

- **Rester indépendant** : aucune modification de `voice_session.py` (Amine K. et les autres y optimisent la vitesse). Seulement des fichiers nouveaux et deux petits crochets dans le code de Mohamed Amine (`process_due`, `_missed`), à lui signaler.
- **Même manière de parler** : on réutilise les règles de style de Lucie, l'ouverture d'appel sortant existante et le format des prix de `rules_order` (`quote`, `say_quantity`). Le SMS garde les symboles (€, %), à l'écrit ce n'est pas gênant.
- **Sûreté** : tout est éteint par défaut (`TEAM_OUTBOUND_AUTO`, `TEAM_OUTBOUND_CHANNEL=dry_run`). Un seul numéro destinataire autorisé, un message au plus par tentative (insertion unique, déjà en place), clés seulement dans `.env` (Youssef les y met lui-même).
- **Twilio en compte d'essai** : un seul numéro vérifié, et le texte commence par « Sent from your Twilio trial account ». Ça suffit pour la démo ; en tests automatiques, rester en `dry_run`.

## 4. Tests (peu mais utiles)

- Unitaires : l'autopilote respecte heures, pause et plafond ; un chiffre inventé fait retomber sur le gabarit ; un seul envoi par tentative ; tout numéro autre que celui de démo est refusé.
- Réels, 3 seulement : (1) appel automatique décroché, conversation avec l'offre ; (2) sans réponse → SMS reçu sur le vrai téléphone ; (3) offre expirée pendant la sonnerie → aucun message.

## 5. À décider / à fournir

- Youssef : un compte Twilio (essai) avec son téléphone vérifié, et dans `.env` : `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM`, `TEAM_OUTBOUND_TEST_PHONE`. Sans compte : lots A et B seulement, message affiché dans la page.
- Mohamed Amine : prévenu des deux crochets dans `outbound_calls.py`.
